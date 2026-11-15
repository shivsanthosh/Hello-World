/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useState } from 'react'
import { api, f, dt } from './api'
import type { Ctx } from './App'
import Viewer from './Viewer'
import { SiteFields } from './Projects'
import { Dcr, statusPill, Mock, useAction, Pill } from './ui'

const TABS = ['Overview', 'Model', 'Engineering', 'Optimisation', 'Review & reports', 'Integrations', 'Audit']

export default function Project({ ctx, meta, id }: { ctx: Ctx; meta: any; id: number }) {
  const [p, setP] = useState<any>(null)
  const [tab, setTab] = useState('Overview')
  const [sel, setSel] = useState<number | null>(null)
  const [products, setProducts] = useState<any[]>([])
  const [sections, setSections] = useState<any[]>([])
  const reload = useCallback(async () => {
    const d = await api(`/projects/${id}`); setP(d)
    setSel(s => (s && d.walls.some((w: any) => w.id === s)) ? s : d.walls[0]?.id ?? null)
  }, [id])
  useEffect(() => { reload(); api('/library/products').then(setProducts); api('/library/sections').then(setSections) }, [reload])
  if (!p) return <div>Loading…</div>
  const can = ctx.user.role !== 'manager'
  const wall = p.walls.find((w: any) => w.id === sel)
  const props = { p, reload, can, wall, sel, setSel, products, sections, ctx, meta }
  return (
    <>
      <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h1>{p.number} · {p.name}</h1>{statusPill(p.status)}<span className="mut small">rev {p.revision} · {p.client} · {p.location}</span>
      </div>
      <div className="tabs">{TABS.map(t => <button key={t} className={t === tab ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === 'Overview' && <Overview {...props} />}
      {tab === 'Model' && <Model {...props} />}
      {tab === 'Engineering' && <Engineering {...props} />}
      {tab === 'Optimisation' && <Optimisation {...props} />}
      {tab === 'Review & reports' && <Review {...props} />}
      {tab === 'Integrations' && <Integrations {...props} />}
      {tab === 'Audit' && <Audit id={id} />}
    </>
  )
}

function WallTable({ p, sel, setSel, products, sections }: any) {
  return <table><thead><tr><th>Wall</th><th>Revit id</th><th className="num">L (m)</th><th className="num">H (m)</th><th className="num">Bay (m)</th><th className="num">Openings</th><th>Panel</th><th>Girt</th><th className="num">Spans</th><th>Calc</th><th>Max DCR</th></tr></thead><tbody>
    {p.walls.map((w: any) => <tr key={w.id} className={'click' + (w.id === sel ? ' sel' : '')} onClick={() => setSel(w.id)}>
      <td><b>{w.name}</b></td><td className="mono">{w.revit_element_id}</td><td className="num">{f(w.length_m)}</td><td className="num">{f(w.height_m)}</td><td className="num">{f(w.max_bay_m)}</td><td className="num">{w.openings.length}</td>
      <td>{products.find((x: any) => x.id === w.product_id)?.name}</td><td>{sections.find((x: any) => x.id === w.section_id)?.name}</td><td className="num">{w.n_spans}</td>
      <td>{w.latest_run ? (w.latest_run.current ? statusPill(w.latest_run.status) : statusPill('stale')) : statusPill(null)}</td><td>{w.latest_run?.current ? <Dcr v={w.latest_run.max_dcr} /> : '—'}</td></tr>)}
  </tbody></table>
}

function Overview({ p, reload, can, meta }: any) {
  const [v, setV] = useState<any>(p)
  const a = useAction(), b = useAction()
  const imp = p.model_import
  const doImport = (data: any) => b.run(async () => { const r = await api(`/projects/${p.id}/import-model`, 'POST', data); await reload(); return r }, 'Model imported.')
  return (
    <>
      <div className="card">
        <h2>Site and wind parameters</h2>
        <SiteFields v={v} set={(k: string, x: any) => setV({ ...v, [k]: x })} meta={meta} />
        <h3>Preparation time measurement (pilot KPI)</h3>
        <div className="grid">
          <label>Baseline preparation hours (current manual process)<input data-testid="f-baseline" type="number" step="any" value={v.baseline_prep_hours ?? ''} onChange={e => setV({ ...v, baseline_prep_hours: e.target.value })} /></label>
          <label>Actual preparation hours (with Panel Studio)<input data-testid="f-actual" type="number" step="any" value={v.actual_prep_hours ?? ''} onChange={e => setV({ ...v, actual_prep_hours: e.target.value })} /></label>
        </div>
        <div className="btns"><button className="b" disabled={!can || a.busy} onClick={() => a.run(async () => { await api(`/projects/${p.id}`, 'PATCH', v); await reload() }, 'Saved. Any change to wind parameters makes existing calculations stale.')}>Save parameters</button></div>
        {a.note}
      </div>
      <div className="card">
        <h2>Revit model import</h2>
        <p className="small mut">Panel Studio reads a JSON export of Revit walls, openings and structural columns (schema <span className="mono">panel-studio-revit-export/1.0</span>). It does not connect to a live Revit session; the export is produced by a Revit add-in or Dynamo script that the BIM team maintains.</p>
        {imp ? <div className="banner ok">Imported {dt(imp.at)} by {imp.imported_by} from <b>{imp.source.model}</b> (Revit {imp.source.version}). {imp.summary.walls_added} added, {imp.summary.walls_updated} updated, {imp.summary.walls_removed} removed, {imp.summary.columns} columns. <span className="mono">sha256 {imp.sha256.slice(0, 16)}…</span></div>
          : <div className="banner warn">No model imported yet.</div>}
        {imp?.summary.warnings.map((w: string) => <div key={w} className="banner warn">{w}</div>)}
        <div className="btns">
          <button className="b" data-testid="import-sample" disabled={!can || b.busy} onClick={async () => doImport(await (await fetch('/api/sample-model')).json())}>Import sample Revit export</button>
          <label style={{ display: 'inline-block' }}><span className="b sec" style={{ display: 'inline-block', padding: '7px 13px', borderRadius: 6, border: '1px solid var(--acc)', color: 'var(--acc)', fontWeight: 600, cursor: 'pointer', fontSize: 14 }}>Upload export (.json)…</span>
            <input type="file" accept=".json" style={{ display: 'none' }} disabled={!can} onChange={async e => { const file = e.target.files?.[0]; if (file) { try { doImport(JSON.parse(await file.text())) } catch { b.run(async () => { throw new Error('File is not valid JSON') }) } } }} /></label>
        </div>
        {b.note}
      </div>
      <div className="card"><h2>Project revision history</h2>
        <table><thead><tr><th>Rev</th><th>When</th><th>User</th><th>Reason</th><th>q (kPa)</th><th>Importance</th><th>h (m)</th></tr></thead><tbody>
          {p.revisions.map((r: any) => <tr key={r.id}><td>{r.revision}</td><td>{dt(r.at)}</td><td>{r.user}</td><td>{r.reason}</td><td>{r.snapshot.q50_kpa}</td><td>{r.snapshot.importance}</td><td>{r.snapshot.ref_height_m}</td></tr>)}
        </tbody></table></div>
    </>
  )
}

function Design({ wall, products, sections, can, reload }: any) {
  const [v, setV] = useState<any>(wall)
  useEffect(() => setV(wall), [wall])
  const a = useAction()
  const dirty = ['product_id', 'section_id', 'n_spans', 'fasteners_per_support'].some(k => Number(v[k]) !== wall[k])
  const save = async () => { if (dirty) await api(`/walls/${wall.id}`, 'PATCH', { product_id: +v.product_id, section_id: +v.section_id, n_spans: +v.n_spans, fasteners_per_support: +v.fasteners_per_support }) }
  return <div className="card">
    <h2>Design — {wall.name}</h2>
    <div className="grid">
      <label>Panel product<select value={v.product_id} onChange={e => setV({ ...v, product_id: e.target.value })}>{products.map((x: any) => <option key={x.id} value={x.id}>{x.name} ({x.evidence_status.toLowerCase()})</option>)}</select></label>
      <label>Girt section<select value={v.section_id} onChange={e => setV({ ...v, section_id: e.target.value })}>{sections.map((x: any) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
      <label>Panel spans (girt lines above base)<input data-testid="f-nspans" type="number" min={1} max={16} value={v.n_spans} onChange={e => setV({ ...v, n_spans: e.target.value })} /></label>
      <label>Fasteners per panel per girt<input type="number" min={1} max={16} value={v.fasteners_per_support} onChange={e => setV({ ...v, fasteners_per_support: e.target.value })} /></label>
    </div>
    <p className="small mut">Girt spacing = {f(wall.height_m / Math.max(1, +v.n_spans), 3)} m · girt span (max column bay) = {f(wall.max_bay_m)} m · openings: {wall.openings.map((o: any) => `${o.kind} ${f(o.width_m, 2)}×${f(o.height_m, 2)}`).join(', ') || 'none'}</p>
    <div className="btns">
      <button className="b sec" disabled={!can || a.busy || !dirty} onClick={() => a.run(async () => { await save(); await reload() }, 'Design saved.')}>Save design</button>
      <button className="b" data-testid="calc-wall" disabled={!can || a.busy} onClick={() => a.run(async () => { await save(); const r = await api(`/walls/${wall.id}/calculate`, 'POST'); await reload(); return r }, 'Calculation complete.')}>Save & calculate</button>
    </div>{a.note}
  </div>
}

function Model(props: any) {
  const { p, wall, sel, setSel, products, sections } = props
  if (!p.walls.length) return <div className="banner warn">Import a Revit export on the Overview tab first.</div>
  return <>
    <div className="card"><Viewer walls={p.walls} products={products} sections={sections} selected={sel} onSelect={setSel} /></div>
    <div className="card"><h2>Walls derived from the Revit export</h2><WallTable {...props} /></div>
    {wall && <Design {...props} />}
  </>
}

function Engineering(props: any) {
  const { p, wall, can, reload } = props
  const [run, setRun] = useState<any>(null)
  const [hist, setHist] = useState<any[]>([])
  const a = useAction()
  const rid = wall?.latest_run?.id
  useEffect(() => { setRun(null); if (rid) api(`/runs/${rid}`).then(setRun); if (wall) api(`/walls/${wall.id}/runs`).then(setHist) }, [rid, wall?.id])
  if (!p.walls.length) return <div className="banner warn">Import a Revit export on the Overview tab first.</div>
  const unv = run?.inputs.evidence.filter((e: any) => e.status !== 'VERIFIED') ?? []
  return <>
    <div className="card"><h2>Calculation status</h2><WallTable {...props} />
      <div className="btns"><button className="b" data-testid="calc-all" disabled={!can || a.busy} onClick={() => a.run(async () => { await api(`/projects/${p.id}/calculate`, 'POST'); await reload() }, 'All walls calculated. Unchanged inputs reuse the existing immutable run.')}>Run all calculations</button></div>{a.note}</div>
    {wall && <Design {...props} />}
    {run && <>
      {!wall.latest_run.current && <div className="banner warn">Inputs changed since this run (revision {run.revision}). Results below are stale — recalculate.</div>}
      {unv.length > 0 && <div className="banner warn"><b>Not for engineering reliance.</b> {unv.length} input record(s) are unverified (e.g. {unv.slice(0, 3).map((e: any) => e.name).join(', ')}). Results are mathematically traceable but depend on data that has not been checked against test reports or the printed code.</div>}
      {run.results.warnings.map((w: string) => <div key={w} className="banner bad">{w}</div>)}
      <div className="card">
        <h2>{run.wall_name} — run revision {run.revision} {statusPill(run.status)}</h2>
        <p className="small mut">Engine v{run.engine_version} · by {run.created_by} at {dt(run.created_at)} · input hash <span className="mono">{run.input_hash}</span></p>
        <h3>Checks</h3>
        <table><thead><tr><th>Check</th><th className="num">Demand</th><th className="num">Capacity</th><th>Unit</th><th style={{ width: 170 }}>Demand / capacity</th><th>Result</th><th>Criterion</th><th>Reference</th></tr></thead><tbody>
          {run.results.checks.map((c: any) => <tr key={c.id}><td>{c.title}</td><td className="num">{f(c.demand, 3)}</td><td className="num">{f(c.capacity, 3)}</td><td>{c.unit}</td><td><Dcr v={c.dcr} /></td><td>{statusPill(c.status)}</td><td>{c.formula}</td><td className="small">{c.reference}</td></tr>)}
        </tbody></table>
        <h3>Calculation trace (formula · substitution · value · unit · source)</h3>
        <div className="scroll"><table><thead><tr><th>Quantity</th><th>Formula</th><th>Substitution</th><th className="num">Value</th><th>Unit</th><th>Reference</th></tr></thead><tbody>
          {run.results.steps.map((s: any) => <tr key={s.id}><td>{s.title}</td><td className="mono">{s.formula}</td><td className="mono">{s.substitution}</td><td className="num"><b>{Number(s.value).toPrecision(4)}</b></td><td>{s.unit}</td><td className="small">{s.reference}</td></tr>)}
        </tbody></table></div>
        <div className="row" style={{ marginTop: 14 }}>
          <div style={{ flex: 1, minWidth: 280 }}><h3>Quantities</h3><table><tbody>{Object.entries(run.results.quantities).map(([k, v]: any) => <tr key={k}><td>{k.replace(/_/g, ' ')}</td><td className="num">{typeof v === 'number' && !Number.isInteger(v) ? f(v, 2) : v}</td></tr>)}</tbody></table></div>
          <div style={{ flex: 2, minWidth: 320 }}><h3>Source evidence for inputs</h3><div className="scroll" style={{ maxHeight: 260 }}><table><thead><tr><th>Record</th><th>Rev</th><th>Status</th><th>Source / evidence reference</th></tr></thead><tbody>
            {run.inputs.evidence.map((e: any) => <tr key={e.kind + e.name}><td>{e.name}</td><td>{e.revision}</td><td>{statusPill(e.status)}</td><td className="small">{e.evidence_ref || e.source}</td></tr>)}</tbody></table></div></div>
        </div>
        <h3>Assumptions and exclusions</h3><ul className="plain small">{run.results.assumptions.map((s: string) => <li key={s}>{s}</li>)}</ul>
        <h3>Run history (immutable)</h3>
        <table><thead><tr><th>Rev</th><th>When</th><th>By</th><th>Status</th><th className="num">Max DCR</th><th>Governing</th><th>Input hash</th></tr></thead><tbody>
          {hist.map(h => <tr key={h.id}><td>{h.revision}</td><td>{dt(h.created_at)}</td><td>{h.created_by}</td><td>{statusPill(h.status)}</td><td className="num">{f(h.max_dcr, 3)}</td><td>{h.summary.governing_title}</td><td className="mono">{h.input_hash.slice(0, 16)}…</td></tr>)}
        </tbody></table>
      </div></>}
    {wall && !run && !rid && <div className="banner warn">No calculation yet for {wall.name}.</div>}
  </>
}

function Optimisation(props: any) {
  const { p, wall, can, reload } = props
  const [o, setO] = useState<any>(null)
  const [onlyFeasible, setOnly] = useState(true)
  const [minS, setMinS] = useState('0.9')
  const a = useAction()
  useEffect(() => { setO(null); if (wall) api(`/walls/${wall.id}/optimizations`).then(l => setO(l[0] ?? null)) }, [wall?.id])
  if (!p.walls.length) return <div className="banner warn">Import a Revit export on the Overview tab first.</div>
  const r = o?.result
  const rows = r ? r.candidates.filter((c: any) => !onlyFeasible || c.feasible).sort((x: any, y: any) => (x.feasible === y.feasible ? x.steel_mass_kg - y.steel_mass_kg : x.feasible ? -1 : 1)) : []
  return <>
    <div className="card"><h2>Select wall</h2><WallTable {...props} /></div>
    {wall && <div className="card">
      <h2>Support-spacing and secondary-steel optimisation — {wall.name}</h2>
      <p className="small mut">Exhaustive enumeration of every girt spacing (H/n) and every girt section in the library. Each candidate is checked by the same engine used for the report; the lightest layout that passes every check wins.</p>
      <label style={{ maxWidth: 260 }}>Minimum practical girt spacing (m)<input data-testid="f-minspacing" type="number" step="0.05" min={0.3} max={6} value={minS} onChange={e => setMinS(e.target.value)} /></label>
      <div className="btns"><button className="b" data-testid="opt-run" disabled={!can || a.busy} onClick={() => a.run(async () => setO(await api(`/walls/${wall.id}/optimize`, 'POST', { min_spacing_m: +minS })), 'Optimisation complete.')}>Run optimisation</button>
        {r?.best && !o.applied && <button className="b" data-testid="opt-apply" disabled={!can || a.busy} onClick={() => a.run(async () => { const x = await api(`/optimizations/${o.id}/apply`, 'POST'); setO(x.optimization); await reload() }, 'Layout applied and wall recalculated.')}>Apply best layout & recalculate</button>}
        {o?.applied && <Pill k="ok">Applied by {o.applied_by} {dt(o.applied_at)}</Pill>}</div>{a.note}
      {r && <>
        <div className="kpis" style={{ marginTop: 14 }}>
          <div className="kpi"><div className="l">Layout before optimisation</div><div className="v">{f(r.baseline.steel_mass_kg, 0)} kg</div><div className="s">{r.baseline.n_spans} spans @ {f(r.baseline.girt_spacing_m, 3)} m · {r.baseline.section_name} · {r.baseline.feasible ? 'passes' : 'FAILS checks'} (DCR {f(r.baseline.max_dcr, 3)})</div></div>
          <div className="kpi"><div className="l">Best feasible layout</div><div className="v">{r.best ? f(r.best.steel_mass_kg, 0) + ' kg' : 'None'}</div><div className="s">{r.best ? `${r.best.n_spans} spans @ ${f(r.best.girt_spacing_m, 3)} m · ${r.best.section_name} · DCR ${f(r.best.max_dcr, 3)}` : 'no candidate passes every check'}</div></div>
          {r.steel_saving_kg !== null ? <div className="kpi"><div className="l">Secondary steel saved</div><div className="v">{f(r.steel_saving_kg, 0)} kg</div><div className="s">{f(r.steel_saving_pct, 1)}% lighter than the passing layout before optimisation</div></div>
            : <div className="kpi"><div className="l">{r.best ? 'Steel added to reach compliance' : 'No feasible layout'}</div><div className="v">{r.best ? `+${f(r.steel_added_for_compliance_kg, 0)} kg` : '—'}</div><div className="s">{r.note}</div></div>}
          <div className="kpi"><div className="l">Search</div><div className="v">{r.search.evaluated}</div><div className="s">candidates evaluated · {r.search.feasible} feasible · n = {r.search.n_spans_min}…{r.search.n_spans_max} × {r.search.sections} sections · min spacing {r.search.min_spacing_m} m</div></div>
        </div>
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}><input type="checkbox" style={{ width: 'auto' }} checked={onlyFeasible} onChange={e => setOnly(e.target.checked)} /> Show feasible candidates only</label>
        <div className="scroll"><table><thead><tr><th className="num">Spans</th><th className="num">Spacing (m)</th><th>Girt</th><th className="num">Steel (kg)</th><th className="num">Fasteners</th><th style={{ width: 160 }}>Max DCR</th><th>Result</th><th>Governing / failed checks</th></tr></thead><tbody>
          {rows.map((c: any, i: number) => <tr key={i} className={r.best && c.n_spans === r.best.n_spans && c.section_id === r.best.section_id ? 'sel' : ''}><td className="num">{c.n_spans}</td><td className="num">{f(c.girt_spacing_m, 3)}</td><td>{c.section_name}</td><td className="num">{f(c.steel_mass_kg, 0)}</td><td className="num">{c.fastener_count}</td><td><Dcr v={c.max_dcr} /></td><td>{statusPill(c.feasible ? 'PASS' : 'FAIL')}</td><td className="small">{c.feasible ? c.governing_check : c.failed_checks.join(', ')}</td></tr>)}
        </tbody></table></div></>}
    </div>}
  </>
}

function Review({ p, can, reload, ctx }: any) {
  const [d, setD] = useState<any>(null)
  const [reports, setReports] = useState<any[]>([])
  const [note, setNote] = useState(''); const [comment, setComment] = useState('')
  const a = useAction()
  const load = useCallback(async () => { setD(await api(`/projects/${p.id}/reviews`)); setReports(await api(`/projects/${p.id}/reports`)); await reload() }, [p.id, reload])
  useEffect(() => { load() }, [load])
  if (!d) return <div>Loading…</div>
  const isEng = ctx.user.role === 'engineer'
  return <>
    <div className="card">
      <h2>Calculation package</h2>
      {d.package_ready ? <div className={'banner ' + (d.all_pass ? 'ok' : 'bad')}>{d.all_pass ? 'All walls have current calculations and pass every check.' : 'Calculations are current but one or more walls fail a check — resolve before submitting.'}</div>
        : <div className="banner warn">One or more walls have missing or stale calculations. Run all calculations on the Engineering tab.</div>}
      <h3>Blockers to “approved for engineering reliance”</h3>
      {d.reliance_blockers.length ? <ul className="plain small">{d.reliance_blockers.map((b: string) => <li key={b}>{b}</li>)}</ul> : <div className="banner ok">None — all input data verified and reference calculations approved.</div>}
      <label>Submission note<input value={note} onChange={e => setNote(e.target.value)} placeholder="Scope of this submission" /></label>
      <div className="btns"><button className="b" data-testid="review-submit" disabled={!can || a.busy || !d.package_ready || !d.all_pass} onClick={() => a.run(async () => { await api(`/projects/${p.id}/reviews`, 'POST', { note }); await load() }, 'Submitted for engineering review.')}>Submit for engineering review</button></div>
    </div>
    <div className="card">
      <h2>Engineering reviews</h2>
      <p className="small mut">Decisions can only be recorded by a user with the engineer role who did not submit the package. Software never approves on its own.</p>
      {d.reviews.length === 0 && <p className="mut">No reviews yet.</p>}
      {d.reviews.map((r: any) => <div key={r.id} style={{ borderTop: '1px solid var(--line)', padding: '10px 0' }}>
        <b>Review rev {r.revision}</b> {statusPill(r.effective_status)} <span className="small mut">submitted by {r.submitted_by} {dt(r.submitted_at)} · {r.run_ids.length} runs · package <span className="mono">{r.package_hash.slice(0, 16)}…</span></span>
        {r.submit_note && <div className="small">Note: {r.submit_note}</div>}
        {r.decided_by && <div className="small">Decision by <b>{r.decided_by}</b> at {dt(r.decided_at)}: {r.decision_comment || '(no comment)'} {r.blockers_at_decision.length > 0 && <span className="mut">· {r.blockers_at_decision.length} reliance blocker(s) open at decision</span>}</div>}
        {r.effective_status === 'SUPERSEDED' && <div className="small mut">Inputs changed after this review; it no longer applies to the current design.</div>}
        {r.effective_status === 'SUBMITTED' && <>
          <label style={{ marginTop: 8 }}>Reviewer comment<input data-testid="review-comment" value={comment} onChange={e => setComment(e.target.value)} /></label>
          <div className="btns">
            <button className="b" data-testid="approve-reliance" disabled={!isEng || a.busy} onClick={() => a.run(async () => { await api(`/reviews/${r.id}/decision`, 'POST', { decision: 'approve_reliance', comment }); await load() }, 'Approved for engineering reliance.')}>Approve for engineering reliance</button>
            <button className="b sec" data-testid="approve-demo" disabled={!isEng || a.busy} onClick={() => a.run(async () => { await api(`/reviews/${r.id}/decision`, 'POST', { decision: 'approve_demo', comment }); await load() }, 'Approved — demonstration only.')}>Approve — demonstration only</button>
            <button className="b danger" disabled={!isEng || a.busy} onClick={() => a.run(async () => { await api(`/reviews/${r.id}/decision`, 'POST', { decision: 'return', comment }); await load() }, 'Returned to coordinator.')}>Return with comments</button>
            {!isEng && <span className="small mut">Switch to an engineer to decide.</span>}
          </div></>}
      </div>)}
      {a.note}
    </div>
    <div className="card">
      <h2>Calculation reports (PDF)</h2>
      <div className="btns" style={{ marginTop: 0, marginBottom: 10 }}><button className="b" data-testid="report-gen" disabled={!can || a.busy || !d.package_ready} onClick={() => a.run(async () => { await api(`/projects/${p.id}/reports`, 'POST'); await load() }, 'Report generated.')}>Generate report for current package</button></div>
      {reports.length ? <table><thead><tr><th>Rev</th><th>Status at issue</th><th>File</th><th>Generated</th><th>By</th><th className="num">Size</th><th>sha256</th></tr></thead><tbody>
        {reports.map(r => <tr key={r.id}><td>{r.revision}</td><td>{statusPill(r.status_label)}</td><td><a href={`/api/reports/${r.id}/download`} target="_blank" rel="noreferrer">{r.filename}</a></td><td>{dt(r.created_at)}</td><td>{r.created_by}</td><td className="num">{(r.size_bytes / 1024).toFixed(0)} kB</td><td className="mono">{r.sha256.slice(0, 16)}…</td></tr>)}
      </tbody></table> : <p className="mut">No reports yet.</p>}
    </div>
  </>
}

function Integrations({ p, can, reload }: any) {
  const [d, setD] = useState<any>(null)
  const [reports, setReports] = useState<any[]>([])
  const a = useAction()
  const load = useCallback(async () => { setD(await api(`/projects/${p.id}/integrations`)); setReports(await api(`/projects/${p.id}/reports`)); await reload() }, [p.id, reload])
  useEffect(() => { load() }, [load])
  if (!d) return <div>Loading…</div>
  const published = new Set(d.forma_docs.map((x: any) => x.report_id))
  const h = d.sap_handoffs[0]
  return <>
    <div className="banner mock"><b>Simulated enterprise systems.</b> {d.note} These screens demonstrate the workflow and data contract only.</div>
    <div className="card"><h2>Salesforce — opportunity status <Mock /></h2>
      {d.salesforce ? <>
        <p><b>{d.salesforce.name}</b> · {d.salesforce.account} · stage {d.salesforce.stage} · <span className="mono">{d.salesforce.sf_id}</span></p>
        <p>Engineering status on opportunity: {d.salesforce.engineering_status ? statusPill(d.salesforce.engineering_status) : <span className="mut">not yet synced</span>} <span className="mut small">(project is currently “{p.status}”)</span></p>
        <div className="btns"><button className="b" data-testid="sf-sync" disabled={!can || a.busy} onClick={() => a.run(async () => { await api(`/projects/${p.id}/integrations/salesforce/sync-status`, 'POST'); await load() }, 'Status written to the mock opportunity.')}>Sync engineering status to opportunity</button></div>
        {d.salesforce.status_log.length > 0 && <table style={{ marginTop: 8 }}><thead><tr><th>When</th><th>Status</th><th>By</th></tr></thead><tbody>{[...d.salesforce.status_log].reverse().map((s: any, i: number) => <tr key={i}><td>{dt(s.at)}</td><td>{s.status}</td><td>{s.by}</td></tr>)}</tbody></table>}
      </> : <p className="mut">This project was entered manually and is not linked to an opportunity.</p>}
    </div>
    <div className="card"><h2>SAP — engineering handoff (staged, never transmitted) <Mock /></h2>
      <p className="small mut">Builds a bill-of-quantities from the approved calculation package and places it in a local outbox. Panel Studio has no endpoint that writes to SAP; production authorization remains in SAP.</p>
      <div className="btns"><button className="b" data-testid="sap-stage" disabled={!can || a.busy} onClick={() => a.run(async () => { await api(`/projects/${p.id}/integrations/sap/handoff`, 'POST'); await load() }, 'Handoff staged in the mock outbox.')}>Stage handoff from approved package</button></div>
      {h && <><p style={{ marginTop: 10 }}>Latest: handoff #{h.id} {statusPill(h.status)} by {h.created_by} {dt(h.created_at)} · approval level {statusPill(h.payload.approval_level)} · engineering reliance: <b>{h.payload.engineering_reliance ? 'yes' : 'no'}</b></p>
        <table><thead><tr><th>Material (mock no.)</th><th>Description</th><th className="num">Quantity</th><th>UoM</th><th>Walls</th></tr></thead><tbody>
          {h.payload.items.map((i: any) => <tr key={i.material_no}><td className="mono">{i.material_no}</td><td>{i.description}</td><td className="num">{i.quantity.toLocaleString()}</td><td>{i.uom}</td><td className="small">{i.walls.length}</td></tr>)}</tbody></table>
        <p className="small mut">{h.payload.production_authorization}</p></>}
    </div>
    <div className="card"><h2>Autodesk Forma Docs — publish report <Mock /></h2>
      {reports.length ? <table><thead><tr><th>Report</th><th>Status at issue</th><th></th></tr></thead><tbody>{reports.map(r => <tr key={r.id}><td>{r.filename}</td><td>{statusPill(r.status_label)}</td>
        <td>{published.has(r.id) ? <Pill k="ok">Published</Pill> : <button className="b sec" data-testid="forma-publish" disabled={!can || a.busy} onClick={() => a.run(async () => { await api(`/projects/${p.id}/integrations/forma/publish`, 'POST', { report_id: r.id }); await load() }, 'Published to the mock document folder.')}>Publish</button>}</td></tr>)}</tbody></table>
        : <p className="mut">Generate a report on the Review & reports tab first.</p>}
      {d.forma_docs.length > 0 && <><h3>Mock document folder</h3><table><thead><tr><th>Folder</th><th>File</th><th>Version</th><th>Uploaded</th><th>By</th><th>sha256</th></tr></thead><tbody>
        {d.forma_docs.map((x: any) => <tr key={x.id}><td className="mono">{x.folder}</td><td>{x.filename}</td><td>V{x.version}</td><td>{dt(x.at)}</td><td>{x.uploaded_by}</td><td className="mono">{x.sha256.slice(0, 16)}…</td></tr>)}</tbody></table></>}
    </div>
    {a.note}
  </>
}

export function Audit({ id }: { id?: number }) {
  const [d, setD] = useState<any>(null)
  useEffect(() => { api('/audit' + (id ? `?project_id=${id}` : '')).then(setD) }, [id])
  if (!d) return <div>Loading…</div>
  return <div className="card"><h2>Audit record</h2>
    <div className={'banner ' + (d.chain.valid ? 'ok' : 'bad')}>{d.chain.valid ? `Hash chain intact across all ${d.chain.events} events (head ${d.chain.head.slice(0, 16)}…).` : `Hash chain BROKEN at event ${d.chain.broken_at_id} — the record has been altered.`}</div>
    <div className="scroll" style={{ maxHeight: 600 }}><table><thead><tr><th>#</th><th>When (UTC)</th><th>User</th><th>Role</th><th>Action</th><th>Entity</th><th>Detail</th><th>Hash</th></tr></thead><tbody>
      {d.events.map((e: any) => <tr key={e.id}><td>{e.id}</td><td style={{ whiteSpace: 'nowrap' }}>{dt(e.at)}</td><td>{e.user}</td><td>{e.role}</td><td><b>{e.action}</b></td><td>{e.entity}</td><td className="mono">{JSON.stringify(e.detail)}</td><td className="mono">{e.hash.slice(0, 10)}…</td></tr>)}
    </tbody></table></div></div>
}
