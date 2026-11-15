/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from 'react'
import { api, getUser, setUser } from './api'
import Dashboard from './Dashboard'
import Projects from './Projects'
import Project from './Project'
import { Library, Validation, AuditPage } from './Admin'

export type Ctx = { user: any; go: (page: string, id?: number) => void }

export default function App() {
  const [users, setUsers] = useState<any[]>([])
  const [uname, setUname] = useState(getUser())
  const [meta, setMeta] = useState<any>(null)
  const [route, setRoute] = useState<{ page: string; id?: number }>(() => {
    const m = location.hash.match(/^#\/(\w+)(?:\/(\d+))?/)
    return m ? { page: m[1], id: m[2] ? Number(m[2]) : undefined } : { page: 'dashboard' }
  })
  useEffect(() => { api('/users').then(setUsers); api('/meta').then(setMeta) }, [])
  const go = (page: string, id?: number) => { location.hash = `#/${page}${id ? '/' + id : ''}`; setRoute({ page, id }) }
  const user = users.find(u => u.username === uname)
  if (!user || !meta) return <div className="main">Loading…</div>
  const ctx: Ctx = { user, go }
  const nav = [['dashboard', 'Executive dashboard'], ['projects', 'Projects'], ['library', 'Engineering library'], ['validation', 'Validation'], ['audit', 'Audit log']]
  return (
    <div className="app">
      <aside className="side">
        <div className="logo">Panel Studio</div>
        <div className="sub">IMP Engineering Studio · engine v{meta.engine_version}</div>
        {nav.map(([k, l]) => <button key={k} className={'nav' + (route.page === k || (k === 'projects' && route.page === 'project') ? ' on' : '')} onClick={() => go(k)}>{l}</button>)}
        <div className="who">
          Acting as
          <select data-testid="user-select" value={uname} onChange={e => { setUser(e.target.value); setUname(e.target.value) }}>
            {users.map(u => <option key={u.username} value={u.username}>{u.name} — {u.title}</option>)}
          </select>
          <div className="note">{meta.auth_note}</div>
        </div>
      </aside>
      <main className="main" key={uname}>
        {route.page === 'dashboard' && <Dashboard ctx={ctx} />}
        {route.page === 'projects' && <Projects ctx={ctx} meta={meta} />}
        {route.page === 'project' && route.id && <Project ctx={ctx} meta={meta} id={route.id} key={route.id} />}
        {route.page === 'library' && <Library ctx={ctx} />}
        {route.page === 'validation' && <Validation ctx={ctx} />}
        {route.page === 'audit' && <AuditPage />}
      </main>
    </div>
  )
}
