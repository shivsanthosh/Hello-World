/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react'

export const Pill = ({ k, children }: { k: string; children: any }) => <span className={'pill ' + k}>{children}</span>
export const statusPill = (s?: string | null) => {
  if (!s) return <Pill k="gray">—</Pill>
  const k = /PASS|VERIFIED$|APPROVED_RELIANCE|Approved for reliance/.test(s) && !/UNVERIFIED/.test(s) ? 'ok'
    : /FAIL|RETURNED|Returned/.test(s) ? 'bad' : /UNVERIFIED|DEMO|demonstration|SUBMITTED|In review|SUPERSEDED|STAGED|stale/i.test(s) ? 'warn' : 'gray'
  return <Pill k={k}>{s.replace(/_/g, ' ')}</Pill>
}
export const Mock = () => <Pill k="mock">MOCK · simulated</Pill>
export const Dcr = ({ v }: { v: number }) => (
  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
    <div className="bar" style={{ flex: 1 }}><i className={v > 1 ? 'bad' : v > 0.9 ? 'mid' : ''} style={{ width: Math.min(v, 1) * 100 + '%' }} /></div>
    <span style={{ width: 42, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{v.toFixed(3)}</span>
  </div>
)

/** Runs an async action, shows its error or success message. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ k: 'ok' | 'bad'; t: string } | null>(null)
  const run = async (fn: () => Promise<any>, ok?: string) => {
    setBusy(true); setMsg(null)
    try { const r = await fn(); if (ok) setMsg({ k: 'ok', t: ok }); return r } catch (e: any) { setMsg({ k: 'bad', t: e.message }) } finally { setBusy(false) }
  }
  const note = msg ? <div className={'banner ' + msg.k} role="status" style={{ marginTop: 10 }}>{msg.t}</div> : null
  return { busy, run, note }
}
