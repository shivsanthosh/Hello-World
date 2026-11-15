/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { api, f, dt } from './api'
import type { Ctx } from './App'
import { statusPill, Mock, useAction } from './ui'

export function SiteFields({ v, set, meta }: { v: any; set: (k: string, x: any) => void; meta: any }) {
  const inp = (k: string, label: string, type = 'number') => <label>{label}<input data-testid={'f-' + k} type={type} step="any" value={v[k] ?? ''} onChange={e => set(k, e.target.value)} /></label>
  const sel = (k: string, label: string) => <label>{label}<select value={v[k]} onChange={e => set(k, e.target.value)}>{meta[k].map((o: string) => <option key={o}>{o}</option>)}</select></label>
  return <div className="grid">
    {inp('name', 'Project name', 'text')}{inp('client', 'Client', 'text')}{inp('location', 'Location', 'text')}
    {inp('q50_kpa', 'q 1/50 reference pressure (kPa)')}{sel('importance', 'Importance category')}{sel('terrain', 'Terrain')}
    {inp('ref_height_m', 'Reference height h (m)')}{inp('least_plan_dim_m', 'Least plan dimension (m)')}{inp('ct', 'Topographic factor Ct')}
    {sel('internal_category', 'Internal pressure')}{inp('climate_source', 'Source of climatic data', 'text')}
  </div>
}

export default function Projects({ ctx, meta }: { ctx: Ctx; meta: any }) {
  const [list, setList] = useState<any[]>([])
  const [opps, setOpps] = useState<any>(null)
  const [v, setV] = useState<any>({ name: '', client: '', location: '', q50_kpa: '', importance: 'Normal', terrain: 'Open', ref_height_m: '', least_plan_dim_m: '', ct: 1, internal_category: 'Category 2', climate_source: '' })
  const a = useAction()
  const load = () => { api('/projects').then(setList); api('/integrations/salesforce/opportunities').then(setOpps) }
  useEffect(load, [])
  const canEdit = ctx.user.role !== 'manager'
  return (
    <>
      <h1>Projects</h1>
      <div className="card">
        <h2>All projects</h2>
        {list.length ? <table><thead><tr><th>Number</th><th>Name</th><th>Client</th><th>Location</th><th className="num">q (kPa)</th><th className="num">Walls</th><th>Status</th><th>Created</th></tr></thead><tbody>
          {list.map(p => <tr key={p.id} className="click" onClick={() => ctx.go('project', p.id)}><td><b>{p.number}</b></td><td>{p.name}</td><td>{p.client}</td><td>{p.location}</td><td className="num">{f(p.q50_kpa)}</td><td className="num">{p.wall_count}</td><td>{statusPill(p.status)}</td><td>{dt(p.created_at)}</td></tr>)}
        </tbody></table> : <p className="mut">No projects yet. Create one from a Salesforce opportunity or enter it manually below.</p>}
      </div>
      <div className="card">
        <h2>Start from a Salesforce opportunity <Mock /></h2>
        {opps && <><div className="banner mock">{opps.note}</div>
          <table><thead><tr><th>Opportunity</th><th>Account</th><th>Stage</th><th className="num">Amount (CAD)</th><th>Site</th><th>Engineering status</th><th></th></tr></thead><tbody>
            {opps.records.map((o: any) => <tr key={o.sf_id}><td><b>{o.name}</b><div className="mono">{o.sf_id}</div></td><td>{o.account}</td><td>{o.stage}</td><td className="num">{o.amount_cad.toLocaleString()}</td>
              <td>{o.site.location} · q {o.site.q50_kpa} kPa · h {o.site.ref_height_m} m</td><td>{o.engineering_status || '—'}</td>
              <td>{o.project_id ? <button className="b sec" onClick={() => ctx.go('project', o.project_id)}>Open project</button>
                : <button className="b" disabled={!canEdit || a.busy} onClick={() => a.run(async () => { const p = await api(`/integrations/salesforce/opportunities/${o.sf_id}/create-project`, 'POST'); ctx.go('project', p.id) })}>Create project</button>}</td></tr>)}
          </tbody></table></>}
      </div>
      <div className="card">
        <h2>New project (manual entry)</h2>
        <SiteFields v={v} set={(k, x) => setV({ ...v, [k]: x })} meta={meta} />
        <div className="btns"><button className="b" disabled={!canEdit || a.busy} onClick={() => a.run(async () => { const p = await api('/projects', 'POST', v); ctx.go('project', p.id) })}>Create project</button>
          {!canEdit && <span className="mut small">Read-only role.</span>}</div>
        {a.note}
      </div>
    </>
  )
}
