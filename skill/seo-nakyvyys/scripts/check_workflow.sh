#!/usr/bin/env bash
# check_workflow.sh - check a Workflow script before starting it (a broken script wastes a launch).
#
# Usage:
#   scripts/check_workflow.sh SCRIPT.js                 parse check + meta is a pure literal
#   scripts/check_workflow.sh SCRIPT.js --mock ARGS.json   also run it offline with stub agents
#   PRINT_LABEL=yhdistys:site scripts/check_workflow.sh SCRIPT.js --mock ARGS.json
#                                                       ...and print that agent's full prompt
#
# The Workflow runtime runs the script body as an async function with the globals
# args, agent, parallel, pipeline, phase and log, so plain `node --check` rejects the
# top-level await and return. This wraps the body the same way and only parses it.
# --mock runs it with stub agents that return schema-shaped placeholders (one item in
# every array of objects, so reviewers report one "estava" finding and the fixer runs);
# no agent, git or network call happens. It prints the agent labels in call order and
# the returned value, and fails when: a prompt lacks a shared rule (Skill tool,
# SendMessage, PID, Docker, pkill, --prod, origin/, vercel curl) or contains
# "undefined", "NaN" or "[object Object]"; an agent or a track throws; no agent is
# called; the script returns an error; a site reports missing implementers or
# reviewers; site port blocks overlap, contain a reserved port or a site has more
# than 8 tasks. Exit 0 = OK, 1 = problem, 64 = usage.

set -euo pipefail
if [ "$#" -lt 1 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
  exit 64
fi

exec node - "$@" <<'JS'
const fs = require('fs')
const vm = require('vm')
const [file, flag, argsFile] = process.argv.slice(2)
const src = fs.readFileSync(file, 'utf8')

const metaMatch = src.match(/^export const meta = (\{[\s\S]*?\n\})/m)
if (!metaMatch) { console.error('FAIL: no "export const meta = {" block ending with a line "}"'); process.exit(1) }
let meta
try { meta = vm.runInNewContext('(' + metaMatch[1] + ')', Object.create(null)) }
catch (e) { console.error('FAIL: meta is not a pure literal: ' + e.message); process.exit(1) }
for (const k of ['name', 'description']) {
  if (typeof meta[k] !== 'string' || !meta[k]) { console.error(`FAIL: meta.${k} missing`); process.exit(1) }
}
if (meta.phases && !Array.isArray(meta.phases)) { console.error('FAIL: meta.phases is not an array'); process.exit(1) }

const body = src.replace(/^export const meta/m, 'const meta')
const AsyncFunction = (async () => {}).constructor
let fn
try { fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', body) }
catch (e) { console.error('FAIL: syntax: ' + e.message); process.exit(1) }
console.log(`OK parse: ${file} (meta.name ${meta.name}, ${(meta.phases || []).length} phases)`)

if (flag !== '--mock') process.exit(0)
if (!argsFile) { console.error('usage: check_workflow.sh SCRIPT.js --mock ARGS.json'); process.exit(64) }
const args = JSON.parse(fs.readFileSync(argsFile, 'utf8'))
const problems = []

// Port blocks and task counts, independent of the script's own checks.
const reserved = new Set(Array.isArray(args.reserved_ports) ? args.reserved_ports : [])
const portOwner = new Map()
for (const s of Array.isArray(args.sites) ? args.sites : []) {
  const id = s.key || s.domain || '?'
  if ((s.tasks || []).length > 8) problems.push(`${id}: ${s.tasks.length} tasks, at most 8 per site`)
  if (!Number.isInteger(s.port)) { problems.push(`${id}: port is not an integer`); continue }
  for (let p = s.port; p < s.port + 10; p++) {
    if (reserved.has(p)) problems.push(`${id}: port ${p} is in reserved_ports`)
    if (portOwner.has(p)) problems.push(`${id}: port ${p} overlaps ${portOwner.get(p)}`)
    portOwner.set(p, id)
  }
}

const RULE_WORDS = ['Skill tool', 'SendMessage', 'PID', 'Docker', 'pkill', '--prod', 'origin/', 'vercel curl']
const stub = (schema, label) => {
  if (!schema) return 'stub text'
  if (schema.enum) return schema.enum[0]
  if (schema.type === 'object') {
    const o = {}
    for (const [k, v] of Object.entries(schema.properties || {})) o[k] = stub(v, label)
    if ('branch' in o) o.branch = 'stub/' + label.replace(/[^a-z0-9-]+/gi, '-')
    return o
  }
  if (schema.type === 'array') return schema.items && schema.items.type === 'object' ? [stub(schema.items, label)] : ['stub']
  if (schema.type === 'string') return 'stub'
  if (schema.type === 'number' || schema.type === 'integer') return 0
  if (schema.type === 'boolean') return false
  return null
}
const calls = []
const agent = async (prompt, opts = {}) => {
  const label = opts.label || '(no label)'
  if (typeof prompt !== 'string' || !prompt.trim()) { problems.push(`${label}: empty prompt`); throw new Error('empty prompt') }
  for (const must of RULE_WORDS) {
    if (!prompt.includes(must)) problems.push(`${label}: prompt lacks the shared rule mentioning "${must}"`)
  }
  const bad = prompt.match(/\bundefined\b|\bNaN\b|\[object Object\]/)
  if (bad) problems.push(`${label}: prompt contains "${bad[0]}" (a missing args field)`)
  calls.push(`${opts.phase || '-'} | ${label} | ${prompt.length} chars`)
  if (process.env.PRINT_LABEL && opts.label === process.env.PRINT_LABEL) console.log(`----- prompt ${opts.label} -----\n${prompt}\n----- end -----`)
  return stub(opts.schema, label)
}
const parallel = async (fns) => Promise.all(fns.map((f) => f().catch((e) => { problems.push('agent error: ' + e.message); return null })))
const pipeline = async (items, ...stages) => Promise.all(items.map(async (item) => {
  try {
    let r = await stages[0](item)
    for (const s of stages.slice(1)) r = await s(r, item)
    return r
  } catch (e) { problems.push('track error: ' + e.message); return undefined }
}))
const phase = () => {}
const log = (m) => console.log('log: ' + m)

fn(args, agent, parallel, pipeline, phase, log).then((ret) => {
  console.log(`agent calls: ${calls.length}`)
  calls.forEach((c) => console.log('  ' + c))
  console.log('returned: ' + JSON.stringify(ret, null, 1).slice(0, 4000))
  if (!calls.length) problems.push('no agent was called')
  if (!Array.isArray(ret)) {
    problems.push('the script returned ' + (ret && ret.error ? 'an error: ' + ret.error : 'no per-site array'))
  } else {
    ret.forEach((r, k) => {
      if (!r) { problems.push(`site ${k}: no result`); return }
      if (r.error) problems.push(`${r.site}: ${r.error}`)
      if (r.implementers_missing) problems.push(`${r.site}: ${r.implementers_missing} implementer(s) missing`)
      if (r.reviewers_missing) problems.push(`${r.site}: ${r.reviewers_missing} reviewer(s) missing`)
    })
  }
  if (problems.length) {
    console.error('FAIL:\n' + [...new Set(problems)].map((p) => '  ' + p).join('\n'))
    process.exit(1)
  }
  console.log('OK mock run')
  process.exit(0)
}).catch((e) => { console.error('FAIL: run threw: ' + e.stack); process.exit(1) })
JS
