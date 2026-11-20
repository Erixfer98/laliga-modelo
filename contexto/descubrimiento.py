"""Catálogo consultado, calendario permitido y correspondencias exactas con Kuota."""
import csv
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from .contratos import SCHEMA, canonico, ahora, utc
from .identidad import pid, apto_para_contexto
from .politica import LIGAS, nombre


class Descubrimiento:
    def __init__(self, client, folder=None):
        self.client = client; self.store = client.store
        self.folder = Path(folder) if folder else Path(__file__).resolve().parents[1] / 'datos'

    def catalogo(self, dry_run=True, cancel=None):
        leagues = {}; states = {}
        for internal, (country, names) in LIGAS.items():
            result = self.client.consultar('/leagues', {'country': country, 'name': names[0]},
                                          purpose='verification', dry_run=dry_run, cancel=cancel)
            states[internal] = result.publico()
            if result.status == 'cancelled': break
            if result.status != 'ok': continue
            body = result.capture.json()
            rows = body['response']
            if not isinstance(rows, list) or len(rows) > 20:
                states[internal] = {'status': 'blocked', 'code': 'catalog_volume_exceeded'}; continue
            if any(not isinstance(r, dict) or not isinstance(r.get('country'), dict) or not isinstance(r.get('league'), dict) or not isinstance(r['country'].get('name'), str) or not isinstance(r['league'].get('name'), str) for r in rows):
                states[internal] = {'status': 'blocked', 'code': 'catalog_contract_invalid'}; continue
            candidates = [r for r in rows if nombre(r.get('country', {}).get('name', '')) == nombre(country)
                          and nombre(r.get('league', {}).get('name', '')) in {nombre(n) for n in names}
                          and r.get('league', {}).get('type') == 'League']
            if len(candidates) != 1:
                states[internal] = {'status': 'blocked', 'code': 'catalog_identity_ambiguous'}; continue
            r = candidates[0]
            try:
                lid = pid(r['league']['id'])
                seasons = r['seasons']
                if not isinstance(seasons, list): raise ValueError('Temporadas inválidas')
                years = [s['year'] for s in seasons]
                if len(years) != len(set(years)) or any(type(y) is not int or not 2000 <= y <= 2100 for y in years): raise ValueError('Temporadas inválidas')
                leagues[internal] = {'provider': 'api-football', 'league_id': lid,
                                     'catalog_record_id': result.record_id, 'seasons': years,
                                     'coverage': {str(s['year']): s.get('coverage', {}) for s in seasons}}
            except (ValueError, KeyError, TypeError):
                states[internal] = {'status': 'blocked', 'code': 'catalog_contract_invalid'}
        # Dos ligas internas no pueden corresponder al mismo ID del proveedor.
        if len({r['league_id'] for r in leagues.values()}) != len(leagues):
            return {}, {'catalog': {'status': 'blocked', 'code': 'catalog_ids_ambiguous'}}
        return leagues, states

    def _mappings(self, cap, row, internal, history):
        data = (self.folder / ('bbdd_' + internal + '.csv')).read_bytes()
        teams = set()
        for r in csv.DictReader(data.decode('utf-8-sig').splitlines()):
            teams.update((r['equipo_local_txt'], r['equipo_visitante_txt']))
        indexed = {}
        for t in teams: indexed.setdefault(nombre(t), []).append(t)
        now = ahora(); proof = canonico({'rule': 'exact_orthographic_v1',
            'source_snapshot_sha256': cap.metadata['sha256'], 'internal_catalog_sha256': sha256(data).hexdigest(), 'internal_team_names': sorted(teams),
            'provider_teams': row['teams']}).encode()
        mappings = []
        for side in ('home', 'away'):
            team = row['teams'][side]
            found = indexed.get(nombre(team['name']), [])
            if len(found) != 1: raise ValueError('Equipo no identificado de forma exacta y única')
            for archived in history:
                g = archived['fixture']
                if g['provider'] != 'api-football' or g['league_id'] != pid(row['league']['id']) or g['season_id'] != pid(row['league']['season']): continue
                for previous in (g['home'], g['away']):
                    if ((previous['provider_team_id'] == pid(team['id'])) != (previous['internal_team'] == found[0])):
                        raise ValueError('Identidad contradictoria entre fixtures')
            kickoff = utc(row['fixture']['date'])
            mappings.append({'schema_version': SCHEMA, 'provider': 'api-football',
                'league_id': pid(row['league']['id']), 'season_id': pid(row['league']['season']),
                'team_id': pid(team['id']), 'internal_team': found[0], 'internal_league': internal,
                'valid_from_utc': (kickoff - timedelta(seconds=1)).isoformat(),
                'valid_until_utc': (kickoff + timedelta(seconds=1)).isoformat(),
                'reviewed_at_utc': now, 'reviewed_by': 'exact_orthographic_v1 (not human certification)',
                'evidence_sha256': sha256(proof).hexdigest()})
        return mappings, proof, now

    def descubrir(self, start, end, seasons, dry_run=True, cancel=None):
        days = self.client.policy.ventana(start, end)
        leagues, states = self.catalogo(dry_run=dry_run, cancel=cancel)
        results = {'catalog': states, 'queries': [], 'accepted': [], 'rejected': [], 'dry_run': dry_run}
        if not leagues: return results
        by_id = {r['league_id']: k for k, r in leagues.items()}
        existing = self.store.archivo.verificar()
        queries = []
        if self.client.policy.strategy == 'league_range':
            for internal, league in leagues.items():
                season = seasons.get(internal)
                if type(season) is not int or season not in league['seasons']:
                    results['rejected'].append({'league': internal, 'code': 'season_not_in_catalog'}); continue
                queries.append({'league': int(league['league_id']), 'season': season, 'from': start, 'to': end})
        else:
            queries = [{'date': day} for day in days]
        for params in queries:
            result = self.client.consultar('/fixtures', params, dry_run=dry_run, cancel=cancel)
            results['queries'].append({'params': params, **result.publico()})
            if result.status == 'cancelled': break
            if result.status != 'ok': continue  # no fallback ni parámetros alternativos
            cap = result.capture; body = cap.json(); rows = body['response']
            limit = self.client.policy.max_global_results if 'date' in params else self.client.policy.max_results
            if not isinstance(rows, list) or len(rows) > limit or body.get('paging', {}).get('total', 1) != 1:
                results['rejected'].append({'code': 'query_volume_or_pagination_not_supported'}); break
            groups = {}
            for row in rows:
                try: groups.setdefault(pid(row['fixture']['id']), []).append(row)
                except (KeyError, ValueError, TypeError): results['rejected'].append({'code': 'fixture_contract_invalid'})
            for fid, copies in groups.items():
                unique = {canonico(r) for r in copies}
                if len(unique) != 1:
                    results['rejected'].append({'fixture_id': fid, 'code': 'duplicate_identity_conflict'}); continue
                row = copies[0]
                try:
                    lid = pid(row['league']['id']); internal = by_id.get(lid)
                    if internal is None: continue
                    season = row['league']['season']
                    if type(season) is not int or season not in leagues[internal]['seasons']:
                        raise ValueError('Temporada fuera de catálogo')
                    if 'league' in params and (int(lid) != params['league'] or season != params['season']):
                        raise ValueError('Fixture de otra consulta')
                    day = utc(row['fixture']['date']).date().isoformat()
                    if not start <= day <= end or ('date' in params and day != params['date']):
                        raise ValueError('Fixture fuera de ventana UTC')
                    # Idénticos repetidos: conservar los bytes originales, no fabricar captura de una fila.
                    mappings, proof, identity_cutoff = self._mappings(cap, row, internal, existing)
                    proof_hash = sha256(proof).hexdigest()
                    old = next((r for r in reversed(existing) if r['fixture']['provider'] == 'api-football' and
                                r['fixture']['fixture_id'] == fid and r['fixture']['snapshot_sha256'] == cap.metadata['sha256'] and
                                {m['evidence_sha256'] for m in r['mappings']} == {proof_hash}), None)
                    receipt = old or self.store.archivo.agregar_fixture(cap, fid, mappings, [proof], identity_cutoff, True)
                    if not old: existing.append(receipt)
                    eligible, reason = apto_para_contexto(receipt, ahora())
                    results['accepted'].append({'fixture_id': fid, 'receipt_id': receipt['receipt_id'],
                        'version': receipt['fixture']['version'], 'eligible_future': eligible, 'reason': reason})
                except (ValueError, KeyError, TypeError):
                    results['rejected'].append({'fixture_id': fid, 'code': 'identity_validation_failed'})
        results['accepted'] = list({r['fixture_id']: r for r in results['accepted']}.values())
        return results

    def inventario(self, cutoff, page=1, page_size=25, future_only=True):
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError('Paginación inválida')
        if utc(cutoff) > utc(ahora()): raise ValueError('Cutoff futuro no admitido')
        latest = {}
        for r in self.store.archivo.verificar():
            if utc(r['registered_at_utc']) <= utc(cutoff):
                latest[(r['fixture']['provider'], r['fixture']['fixture_id'])] = r
        rows = []
        for r in latest.values():
            eligible, reason = apto_para_contexto(r, cutoff)
            if future_only and not eligible: continue
            rows.append({**r['fixture'], 'receipt_id': r['receipt_id'], 'registered_at_utc': r['registered_at_utc'],
                         'eligible_future': eligible, 'reason': reason})
        rows.sort(key=lambda r: (r['kickoff_utc'], r['provider'], r['fixture_id']))
        return {'as_of_utc': cutoff, 'page': page, 'page_size': page_size, 'total': len(rows),
                'pages': (len(rows) + page_size - 1) // page_size,
                'inventory_version': sha256(canonico([r['receipt_id'] for r in rows]).encode()).hexdigest(),
                'fixtures': rows[(page - 1) * page_size:page * page_size]}
