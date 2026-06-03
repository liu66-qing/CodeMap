import { useEffect, useState } from 'react'
import { NavLink as RouterNavLink, useLocation, useSearchParams } from 'react-router-dom'
import { AppShell, Burger, Group, Progress, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { HelpCircle, Home, Map, MessageCircle, Pickaxe, Settings, Signpost, Swords, Trophy } from 'lucide-react'
import { api } from '../../services/api'
import ChatSidebar from '../chat/ChatSidebar'
import PixelLogo from './PixelLogo'
import LanguageToggle from './LanguageToggle'
import { useLanguage } from '../../i18n/LanguageContext'
import characterSheet from '../../assets/pixel/characters/kenney-characters.png'

const mainRoutes = [
  { path: '/', labelKey: 'nav.home', icon: Home, end: true },
  { path: '/map', labelKey: 'nav.map', icon: Map },
  { path: '/overview', labelKey: 'nav.overview', icon: Signpost, badge: '1' },
  { path: '/mainflow', labelKey: 'nav.mainflow', icon: Trophy, badge: '2' },
  { path: '/showcase', labelKey: 'nav.showcase', icon: Swords, badge: '3' },
  { path: '/takeaway', labelKey: 'nav.takeaway', icon: Pickaxe, badge: '4' },
]

const supportRoutes = [
  { labelKey: 'nav.settings', icon: Settings },
  { labelKey: 'nav.help', icon: HelpCircle },
  { labelKey: 'nav.feedback', icon: MessageCircle },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const [activeRepo, setActiveRepo] = useState('')
  const [opened, { toggle, close }] = useDisclosure()
  const { t } = useLanguage()

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
            <Text className="cg-brand-name">CodeMap</Text>
          </div>

          <nav className="cg-main-nav" aria-label={t('nav.mainNavLabel')}>
            {mainRoutes.map(({ path, labelKey, icon: Icon, end, badge }) => {
              const active = end ? location.pathname === path : location.pathname === path
              return (
                <RouterNavLink key={path} to={path} onClick={close} className={active ? 'cg-nav-item is-active' : 'cg-nav-item'}>
                  <Icon size={30} strokeWidth={2.4} />
                  <span>{t(labelKey)}</span>
                  {badge && <em>{badge}</em>}
                </RouterNavLink>
              )
            })}
          </nav>

          <div className="cg-sidebar-divider" />

          <nav className="cg-support-nav" aria-label={t('nav.supportNavLabel')}>
            {supportRoutes.map(({ labelKey, icon: Icon }) => (
              <button key={labelKey} type="button" className="cg-support-item">
                <Icon size={27} />
                <span>{t(labelKey)}</span>
              </button>
            ))}
            <LanguageToggle />
          </nav>

          <div className="cg-user-card">
            <div className="cg-user-row">
              <div className="cg-user-avatar" style={{ backgroundImage: `url(${characterSheet})` }} />
              <div>
                <strong>coder_01</strong>
                <span>{t('user.greeting')}</span>
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
            <Text fw={800}>CodeMap</Text>
          </Group>
          <Burger opened={opened} onClick={toggle} size="sm" color="#fff" />
        </Group>
      </AppShell.Header>

      <AppShell.Main className="cg-app-main">{children}</AppShell.Main>
      {activeRepo && <ChatSidebar repoId={activeRepo} />}
    </AppShell>
  )
}
