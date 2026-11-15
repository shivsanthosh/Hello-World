/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { api, f } from './api'
import type { Ctx } from './App'
import { Dcr, statusPill, Pill } from './ui'

export default function Dashboard({ ctx }: { ctx: Ctx }) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api('/dashboard').then(setD) }, [])
  if (!d) return <div>Loading…</div>
  const pt = d.prep_time, st = d.steel
  return (
    <>
      <h1>Executive dashboard</h1>
      <p className="mut">Every figure is computed from stored project records. Nothing on this page is a forecast.</p>
      <div className="kpis">
        <div className="kpi"><div className="l">Projects</div><div className="v">{d.projects}</div><div className="s">{Object.entries(d.by_status).map(([k, v]) => `${v} ${k}`).join(' · ') || 'none yet'}</div></div>
        <div className="kpi"><div className="l">Walls passing all checks</div><div className="v">{d.walls_passing} / {d.walls}</div><div className="s">{d.walls_current} with current calculations · {d.calc_runs} calc runs retained</div></div>
        <div className="kpi"><div className="l">Secondary steel saved by optimisation</div><div className="v">{st.compared_to_passing_baseline ? `${f(st.saved_kg, 0)} kg` : '—'}</div>
          <div className="s">{st.compared_to_passing_baseline ? `${f(st.saved_pct, 1)}% of ${f(st.baseline_kg, 0)} kg on ${st.compared_to_passing_baseline} wall(s) whose prior layout already passed` : 'no optimisation applied to a passing layout yet'}
            {st.failing_layouts_corrected > 0 && ` · ${st.failing_layouts_corrected} failing layout(s) corrected (not counted as savings)`}</div></div>
        <div className="kpi"><div className="l">Preparation time reduction (target {pt.target_pct}%)</div><div className="v">{pt.reduction_pct === null ? 'Not measured' : f(pt.reduction_pct, 1) + '%'}</div>
          <div className="s">{pt.projects_measured ? `${f(pt.actual_hours, 1)} h actual vs ${f(pt.baseline_hours, 1)} h baseline on ${pt.projects_measured} project(s)` : 'enter baseline and actual hours on a project'} · {pt.basis}</div></div>
        <div className="kpi"><div className="l">Engineering reviews</div><div className="v">{d.reviews.approved_reliance + d.reviews.approved_demo}</div>
          <div className="s">{d.reviews.approved_reliance} for reliance · {d.reviews.approved_demo} demonstration-only · {d.reviews.submitted} open · {d.reviews.returned} returned</div></div>
        <div className="kpi"><div className="l">Audit chain</div><div className="v">{d.audit.valid ? 'Intact' : 'BROKEN'}</div><div className="s">{d.audit.events} hash-chained events · {d.reports} reports issued</div></div>
      </div>
      <div className="row">
        <div className="card">
          <h2>Readiness for engineering reliance (gate G0)</h2>
          <table><thead><tr><th>Evidence</th><th>Verified</th><th style={{ width: '45%' }}>Progress</th></tr></thead><tbody>
            {d.evidence.map((e: any) => <tr key={e.label}><td>{e.label}</td><td>{e.verified} / {e.total}</td>
              <td><div className="bar"><i className={e.verified < e.total ? 'mid' : ''} style={{ width: (e.total ? e.verified / e.total * 100 : 0) + '%' }} /></div></td></tr>)}
          </tbody></table>
          <p className="small mut">Until every row is complete, approvals are limited to “demonstration only” and reports are watermarked.</p>
          <h3>Pilot safeguards enforced in software</h3>
          <ul className="plain small">{d.safeguards.map((s: string) => <li key={s}>{s}</li>)}</ul>
        </div>
        <div className="card">
          <h2>Wall utilisation (current calculations)</h2>
          {d.dcrs.length ? <div className="scroll"><table><thead><tr><th>Project</th><th>Wall</th><th>Status</th><th style={{ width: '30%' }}>Max demand/capacity</th><th>Governing check</th></tr></thead><tbody>
            {d.dcrs.map((r: any, i: number) => <tr key={i}><td>{r.project}</td><td>{r.wall}</td><td>{statusPill(r.status)}</td><td><Dcr v={r.max_dcr} /></td><td>{r.governing}</td></tr>)}
          </tbody></table></div> : <p className="mut">No current calculations. <button className="b sec" onClick={() => ctx.go('projects')}>Open projects</button></p>}
          <p className="small mut" style={{ marginTop: 8 }}><Pill k="mock">MOCK</Pill> Salesforce, SAP and Forma Docs shown in this application are local simulations.</p>
        </div>
      </div>
    </>
  )
}
