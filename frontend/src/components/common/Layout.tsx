import { useEffect, useState } from 'react'
import { NavLink as RouterNavLink, useLocation, useSearchParams } from 'react-router-dom'
import { AppShell, Burger, Group, Progress, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { HelpCircle, Home, Map, MessageCircle, Pickaxe, Settings, Signpost, Swords, Trophy } from 'lucide-react'
import { api } from '../../services/api'
import ChatSidebar from '../chat/ChatSidebar'
import PixelLogo from './PixelLogo'
import characterSheet from '../../assets/pixel/characters/kenney-characters.png'

const mainRoutes = [
  { path: '/', label: '首页', icon: Home, end: true },
  { path: '/map', label: '学习地图', icon: Map },
  { path: '/overview', label: '先看门道', icon: Signpost, badge: '1' },
  { path: '/mainflow', label: '跑通主线', icon: Trophy, badge: '2' },
  { path: '/showcase', label: '拆它绝活', icon: Swords, badge: '3' },
  { path: '/takeaway', label: '抄走一招', icon: Pickaxe, badge: '4' },
]

const supportRoutes = [
  { label: '设置', icon: Settings },
  { label: '帮助中心', icon: HelpCircle },
  { label: '反馈建议', icon: MessageCircle },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [activeRepo, setActiveRepo] = useState('')
  const [opened, { toggle, close }] = useDisclosure()

  useEffect(() => {
    const fromUrl = searchParams.get('repo')
    if (fromUrl) {
      setActiveRepo(fromUrl)
      return
    }
    api.listRepos().then((r) => {
      const ids = (r.repositories || []).map((x) => x.repo_id)
      if (ids.length && !activeRepo) setActiveRepo(ids[0])
    }).catch(() => {})
  }, [searchParams, activeRepo])

  return (
    <AppShell
      navbar={{ width: { base: 0, sm: 248, md: 248 }, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding={0}
    >
      <AppShell.Navbar p={0} className="cg-sidebar">
        <div className="cg-sidebar-inner">
          <div className="cg-sidebar-brand">
            <PixelLogo size={42} />
            <Text className="cg-brand-name">CodeGraph</Text>
          </div>

          <nav className="cg-main-nav" aria-label="主导航">
            {mainRoutes.map(({ path, label, icon: Icon, end, badge }) => {
              const active = end ? location.pathname === path : location.pathname === path
              return (
                <RouterNavLink key={path} to={path} onClick={close} className={active ? 'cg-nav-item is-active' : 'cg-nav-item'}>
                  <Icon size={30} strokeWidth={2.4} />
                  <span>{label}</span>
                  {badge && <em>{badge}</em>}
                </RouterNavLink>
              )
            })}
          </nav>

          <div className="cg-sidebar-divider" />

          <nav className="cg-support-nav" aria-label="辅助导航">
            {supportRoutes.map(({ label, icon: Icon }) => (
              <button key={label} type="button" className="cg-support-item">
                <Icon size={27} />
                <span>{label}</span>
              </button>
            ))}
          </nav>

          <div className="cg-user-card">
            <div className="cg-user-row">
              <div className="cg-user-avatar" style={{ backgroundImage: `url(${characterSheet})` }} />
              <div>
                <strong>coder_01</strong>
                <span>老乡，继续进步！</span>
              </div>
            </div>
            <div className="cg-xp">💎 1280 / 2000 XP</div>
            <Progress value={72} radius="xl" size={14} />
          </div>
        </div>
      </AppShell.Navbar>

      <AppShell.Header className="cg-mobile-header" hiddenFrom="sm">
        <Group h="100%" px={16} justify="space-between">
          <Group gap={8}>
            <PixelLogo size={32} />
            <Text fw={800}>CodeGraph</Text>
          </Group>
          <Burger opened={opened} onClick={toggle} size="sm" color="#fff" />
        </Group>
      </AppShell.Header>

      <AppShell.Main className="cg-app-main">{children}</AppShell.Main>
      {activeRepo && <ChatSidebar repoId={activeRepo} />}
    </AppShell>
  )
}
