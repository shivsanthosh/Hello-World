/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { api, f, dt } from './api'
import type { Ctx } from './App'
import { statusPill, useAction } from './ui'
import { Audit } from './Project'

const PF = [['Mr_kNm_per_m', 'Mr (kN·m/m)'], ['Vr_kN_per_m', 'Vr (kN/m)'], ['fastener_Tr_kN', 'Fastener Tr (kN)'], ['max_span_m', 'Max span (m)'], ['G_core_MPa', 'Core G (MPa)'], ['face_ext_mm', 'Ext. face (mm)'], ['face_int_mm', 'Int. face (mm)']]

function Evidence({ kind, o, isEng, reload }: any) {
  const [ref, setRef] = useState('')
  const a = useAction()
  return <div style={{ minWidth: 230 }}>{statusPill(o.evidence_status)} <span className="small mut">rev {o.revision}</span>
    {o.evidence_status === 'VERIFIED' ? <div className="small">{o.evidence_ref}<div className="mut">by {o.verified_by} {dt(o.verified_at)}</div></div>
      : <div style={{ display: 'flex', gap: 4, marginTop: 4 }}><input data-testid="evidence-ref" placeholder="Test report / clause checked" value={ref} onChange={e => setRef(e.target.value)} />
        <button className="b sec" disabled={!isEng || a.busy} onClick={() => a.run(async () => { await api(`/library/${kind}/${o.id}/verify`, 'POST', { evidence_ref: ref }); await reload() })}>Verify</button></div>}
    {a.note}</div>
}

export function Library({ ctx }: { ctx: Ctx }) {
  const [d, setD] = useState<any>(null)
  const [edit, setEdit] = useState<any>(null)
  const a = useAction()
  const isEng = ctx.user.role === 'engineer'
  const load = async () => { const [products, sections, codes] = await Promise.all([api('/library/products'), api('/library/sections'), api('/library/code-values')]); setD({ products, sections, codes }) }
  useEffect(() => { load() }, [])
  if (!d) return <div>Loading…</div>
  return <>
    <h1>Engineering library</h1>
    <div className="banner warn">Seeded strengths are <b>illustrative demonstration values, not manufacturer data</b>. Code tables are transcriptions awaiting check against the printed standards. Only an engineer can edit or verify; editing a record resets its verification and creates a new revision.</div>
    {!isEng && <div className="banner mock" style={{ background: '#e9edf2', color: '#5d6b7e' }}>Read-only for your role. Switch to an engineer to edit or verify records.</div>}
    <div className="card"><h2>IMP panel products</h2>
      <table><thead><tr><th>Product</th>{PF.map(([, l]) => <th key={l} className="num">{l}</th>)}<th className="num">EI (kN·m²/m)</th><th className="num">GA (kN/m)</th><th>Source</th><th>Evidence</th><th></th></tr></thead><tbody>
        {d.products.map((p: any) => <tr key={p.id}><td><b>{p.name}</b><div className="small mut">{p.thickness_mm} mm · module {p.module_mm} mm</div></td>
          {PF.map(([k]) => <td key={k} className="num">{edit?.id === p.id ? <input style={{ width: 70 }} type="number" step="any" value={edit[k] ?? ''} onChange={e => setEdit({ ...edit, [k]: e.target.value === '' ? null : +e.target.value })} /> : (p[k] ?? '—')}</td>)}
          <td className="num" title="Derived: E·A1·A2/(A1+A2)·e²">{f(p.derived.EI_kNm2_per_m, 1)}</td><td className="num" title="Derived: G·b·e²/dc">{f(p.derived.GA_kN_per_m, 1)}</td>
          <td className="small" style={{ maxWidth: 220 }}>{p.source}</td><td><Evidence kind="products" o={p} isEng={isEng} reload={load} /></td>
          <td>{edit?.id === p.id ? <><button className="b" disabled={a.busy} onClick={() => a.run(async () => { await api(`/library/products/${p.id}`, 'PATCH', Object.fromEntries(PF.map(([k]) => [k, edit[k]]))); setEdit(null); await load() })}>Save</button> <button className="b sec" onClick={() => setEdit(null)}>Cancel</button></>
            : <button className="b sec" disabled={!isEng} onClick={() => setEdit({ ...p })}>Edit</button>}</td></tr>)}
      </tbody></table>{a.note}
      <p className="small mut">EI and GA are calculated from face thickness and core shear modulus (sandwich theory). Strengths are test-derived and can only come from this record.</p></div>
    <div className="card"><h2>Girt sections (cold-formed)</h2>
      <table><thead><tr><th>Section</th><th className="num">D × B × lip × t (mm)</th><th className="num">Fy (MPa)</th><th className="num">A (mm²)</th><th className="num">Ix (10⁶ mm⁴)</th><th className="num">Sx (10³ mm³)</th><th className="num">kg/m</th><th>Evidence</th></tr></thead><tbody>
        {d.sections.map((s: any) => <tr key={s.id}><td><b>{s.name}</b></td><td className="num">{s.depth_mm} × {s.flange_mm} × {s.lip_mm} × {s.t_mm}</td><td className="num">{s.Fy_MPa}</td><td className="num">{f(s.derived.A_mm2, 0)}</td><td className="num">{f(s.derived.Ix_mm4 / 1e6, 3)}</td><td className="num">{f(s.derived.Sx_mm3 / 1e3, 2)}</td><td className="num">{f(s.derived.mass_kg_per_m, 2)}</td><td><Evidence kind="sections" o={s} isEng={isEng} reload={load} /></td></tr>)}
      </tbody></table><p className="small mut">Section properties are computed from geometry (gross, thin-wall centreline method) — they are not typed in.</p></div>
    <div className="card"><h2>Code and criteria tables</h2>
      <table><thead><tr><th>Key</th><th>Value</th><th>Source</th><th>Evidence</th></tr></thead><tbody>
        {d.codes.map((c: any) => <tr key={c.id}><td className="mono">{c.key}</td><td className="mono" style={{ maxWidth: 380 }}>{JSON.stringify(c.value)} <span className="mut">[{c.unit}]</span></td><td className="small">{c.source}</td><td><Evidence kind="code-values" o={c} isEng={isEng} reload={load} /></td></tr>)}
      </tbody></table></div>
  </>
}

export function Validation({ ctx }: { ctx: Ctx }) {
  const [cases, setCases] = useState<any[] | null>(null)
  const a = useAction()
  const load = () => api('/validation/cases').then(setCases)
  useEffect(() => { load() }, [])
  if (!cases) return <div>Loading…</div>
  const isEng = ctx.user.role === 'engineer'
  const pass = cases.filter(c => c.result.passed).length, appr = cases.filter(c => c.approved_by).length
  return <>
    <h1>Engine validation</h1>
    <p className="mut">Each reference case is re-executed against the live engine every time this page loads. A case counts toward engineering reliance only after an engineer other than its author has independently confirmed the expected values.</p>
    <div className="kpis"><div className="kpi"><div className="l">Cases passing now</div><div className="v">{pass} / {cases.length}</div></div><div className="kpi"><div className="l">Independently approved</div><div className="v">{appr} / {cases.length}</div></div></div>
    {cases.map(c => <div className="card" key={c.id}>
      <h2>{c.title} {statusPill(c.result.passed ? 'PASS' : 'FAIL')} {c.approved_by ? statusPill('VERIFIED') : statusPill('UNVERIFIED')}</h2>
      <p className="small mut">{c.source} · inputs <span className="mono">{JSON.stringify(c.inputs)}</span> · tolerance {c.rel_tol * 100}%{c.approved_by && ` · approved by ${c.approved_by} ${dt(c.approved_at)}`}</p>
      {c.result.error && <div className="banner bad">{c.result.error}</div>}
      <table><thead><tr><th>Quantity</th><th className="num">Reference value</th><th className="num">Engine value</th><th className="num">Relative error</th><th>Result</th></tr></thead><tbody>
        {c.result.rows.map((r: any) => <tr key={r.quantity}><td>{r.quantity}</td><td className="num">{Number(r.expected).toPrecision(7)}</td><td className="num">{Number(r.engine).toPrecision(7)}</td><td className="num">{r.rel_error.toExponential(1)}</td><td>{statusPill(r.passed ? 'PASS' : 'FAIL')}</td></tr>)}</tbody></table>
      {!c.approved_by && <div className="btns"><button className="b sec" disabled={!isEng || a.busy} onClick={() => a.run(async () => { await api(`/validation/cases/${c.id}/approve`, 'POST'); await load() })}>Record independent approval</button></div>}
    </div>)}
    {a.note}
  </>
}

export function AuditPage() { return <><h1>Audit log</h1><Audit /></> }
