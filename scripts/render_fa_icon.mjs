#!/usr/bin/env node

import { findIconDefinition, icon, library } from '@fortawesome/fontawesome-svg-core'
import { fab } from '@fortawesome/free-brands-svg-icons'
import { far } from '@fortawesome/free-regular-svg-icons'
import { fas } from '@fortawesome/free-solid-svg-icons'

library.add(fas, far, fab)

const rawName = process.argv[2] || ''
const key = rawName.trim().toLowerCase()

if (!key) {
  process.exit(1)
}

function parseIconSpec(spec) {
  const tokens = spec.split(/\s+/).filter(Boolean)
  let preferredPrefixes = []
  let iconName = ''

  for (const token of tokens) {
    if (token === 'fa-solid') {
      preferredPrefixes = ['fas']
    } else if (token === 'fa-regular') {
      preferredPrefixes = ['far']
    } else if (token === 'fa-brands') {
      preferredPrefixes = ['fab']
    } else if (token.startsWith('fa-') && token !== 'fa-fw') {
      iconName = token.slice(3)
    } else if (token !== 'fa') {
      iconName = token
    }
  }

  if (!preferredPrefixes.length) {
    preferredPrefixes = ['fas', 'far', 'fab']
  }

  return { preferredPrefixes, iconName }
}

const { preferredPrefixes, iconName } = parseIconSpec(key)

if (!iconName) {
  process.exit(1)
}

const iconDef = preferredPrefixes
  .map(prefix => findIconDefinition({ prefix, iconName }))
  .find(Boolean)

if (!iconDef) {
  process.exit(2)
}

const rendered = icon(iconDef, {
  classes: ['icon-fa', 'fa-fw'],
  attributes: { width: 16, height: 16 },
})

process.stdout.write(rendered.html[0] || '')
