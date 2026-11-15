/* eslint-disable @typescript-eslint/no-explicit-any */
let currentUser = localStorage.getItem('ps.user') || 'tcoord'
export const getUser = () => currentUser
export const setUser = (u: string) => { currentUser = u; localStorage.setItem('ps.user', u) }

export async function api(path: string, method = 'GET', body?: unknown): Promise<any> {
  const r = await fetch('/api' + path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-User': currentUser },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    let msg = r.statusText
    try {
      const j = await r.json()
      const d = j.detail
      msg = typeof d === 'string' ? d : d?.message ? `${d.message}: ${(d.blockers || []).join('; ')}` : JSON.stringify(d)
    } catch { /* keep status text */ }
    throw new Error(msg)
  }
  return r.json()
}

export const f = (x: number | null | undefined, n = 2) => (x === null || x === undefined ? '–' : Number(x).toFixed(n))
export const dt = (s?: string | null) => (s ? s.slice(0, 19).replace('T', ' ') : '–')
