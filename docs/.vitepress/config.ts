import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'ProxyBox',
  description: 'Per-device isolated home / personal proxy management panel',
  lang: 'zh-CN',
  cleanUrls: true,

  themeConfig: {
    nav: [
      { text: 'Getting started', link: '/getting-started' },
      { text: 'Architecture', link: '/architecture' },
      { text: 'Deploy', link: '/deploy/install-sh' },
      { text: 'GitHub', link: 'https://github.com/carlos0xx/proxybox' },
    ],

    sidebar: [
      {
        text: 'Intro',
        items: [
          { text: 'Overview', link: '/' },
          { text: 'Getting started', link: '/getting-started' },
          { text: 'Architecture', link: '/architecture' },
        ],
      },
      {
        text: 'Deploy',
        items: [
          { text: 'install.sh', link: '/deploy/install-sh' },
          { text: 'Docker Compose', link: '/deploy/docker' },
          { text: 'Claude Skill', link: '/deploy/claude-skill' },
        ],
      },
      {
        text: 'API',
        items: [
          { text: 'Endpoints', link: '/api/endpoints' },
          { text: 'Subscription URLs', link: '/api/subscription' },
        ],
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/carlos0xx/proxybox' },
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'ProxyBox contributors',
    },
  },
})
