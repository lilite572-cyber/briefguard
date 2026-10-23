#!/usr/bin/env node
/* Dependency-free checks of the real inline workbench script in a small DOM stub.
 * These tests do not establish browser rendering, file download or clipboard QA.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'web/workbench.html');
const html = fs.readFileSync(sourcePath, 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert.equal(scripts.length, 1, 'Expected exactly one inline application script');
const source = scripts[0][1];
const compiled = new vm.Script(source, {filename: 'web/workbench.html:inline'});
const defaults = {
  format: 'gif', inputPath: '/tmp/clip.gif', fps: '24',
  requirements: 'Keep product visible.\nNo overlay.',
  requirementsPath: 'requirements.json', method: 'uniform', budget: '8',
  outputPath: 'results/private-test', responsePath: '/tmp/response.json'
};
const nodes = {};
function element(id) {
  if (!nodes[id]) nodes[id] = {
    value: defaults[id] || '', textContent: '', hidden: false, disabled: false,
    handlers: {}, addEventListener(event, callback) { this.handlers[event] = callback; }
  };
  return nodes[id];
}
const context = vm.createContext({document: {getElementById: element}});
compiled.runInContext(context, {timeout: 1000});
const checks = [];
function check(name, test) {
  for (const [id, value] of Object.entries(defaults)) element(id).value = value;
  vm.runInContext('build()', context, {timeout: 1000});
  test();
  checks.push(name);
}
function change(id, value) {
  element(id).value = value;
  element(id).handlers.input();
}
function enabled() { assert.equal(element('copyPrepare').disabled, false); }
function rejected() { assert.equal(element('copyPrepare').disabled, true); }

check('inline_script_parses_and_initial_command_is_ready', () => {
  enabled();
  assert.match(element('prepareCommand').textContent, /^python -m briefguard\.workflow prepare /);
});
check('requirements_are_trimmed_and_blank_lines_omitted', () => {
  change('requirements', '  Keep product visible.  \n\n No overlay. ');
  assert.deepEqual(JSON.parse(element('requirementsPreview').textContent), {
    rule_1: 'Keep product visible.', rule_2: 'No overlay.'
  });
});
check('requirements_html_and_quotes_remain_plain_json', () => {
  const value = '<img src=x onerror=alert(1)> "quoted" & exact';
  change('requirements', value);
  assert.equal(JSON.parse(element('requirementsPreview').textContent).rule_1, value);
});
check('shell_apostrophe_and_command_substitution_are_quoted_in_all_paths', () => {
  const attack = "/tmp/Amir's $(printf BAD); `printf BAD` clip";
  for (const id of ['inputPath', 'requirementsPath', 'outputPath', 'responsePath']) change(id, attack);
  const quoted = "'/tmp/Amir'\\''s $(printf BAD); `printf BAD` clip'";
  assert.equal(element('prepareCommand').textContent,
    'python -m briefguard.workflow prepare --input '+quoted+' --requirements '+quoted+
    ' --out '+quoted+' --method uniform --budget 8');
  assert.equal(element('importCommand').textContent,
    'python -m briefguard.workflow import-response --directory '+quoted+' --response '+quoted);
  assert.equal(element('executeCommand').textContent,
    'python -m briefguard.workflow execute --directory '+quoted+' --approve-openai-gpt41mini-usd050');
  enabled();
});
for (const value of ['1', '32']) check('budget_accepts_'+value, () => {change('budget', value); enabled();});
for (const value of ['0', '33', '1.5', '', 'NaN']) check('budget_rejects_'+JSON.stringify(value), () => {change('budget', value); rejected();});
check('png_adds_explicit_fps', () => {
  change('format', 'png');
  assert.equal(element('fpsBlock').hidden, false);
  assert.match(element('prepareCommand').textContent, / --fps 24$/);
  enabled();
});
for (const value of ['0.001', '1000']) check('png_fps_accepts_'+value, () => {
  change('format', 'png'); change('fps', value); enabled();
});
for (const value of ['0', '-1', '1000.1', '', 'Infinity']) check('png_fps_rejects_'+JSON.stringify(value), () => {
  change('format', 'png'); change('fps', value); rejected();
});
check('gif_does_not_add_fps_override', () => {
  change('fps', '0'); enabled();
  assert.equal(element('fpsBlock').hidden, true);
  assert.equal(element('prepareCommand').textContent.includes('--fps'), false);
});
check('empty_requirements_disable_download_and_prepare', () => {
  change('requirements', ' \n '); rejected(); assert.equal(element('download').disabled, true);
});
check('fifty_requirements_accepted', () => {
  change('requirements', Array.from({length: 50}, (_, i) => 'Requirement '+i).join('\n'));
  enabled(); assert.equal(element('download').disabled, false);
});
check('fifty_one_requirements_rejected', () => {
  change('requirements', Array.from({length: 51}, (_, i) => 'Requirement '+i).join('\n'));
  rejected(); assert.equal(element('download').disabled, true);
});
check('two_thousand_character_requirement_accepted', () => {change('requirements', 'x'.repeat(2000)); enabled();});
check('oversize_requirement_rejected', () => {
  change('requirements', 'x'.repeat(2001)); rejected(); assert.equal(element('download').disabled, true);
});
for (const value of ['', '\n', '/tmp/a\nb', '/tmp/a\0b']) check('invalid_path_rejected_'+JSON.stringify(value), () => {
  change('outputPath', value); rejected(); assert.equal(element('copyImport').disabled, true); assert.equal(element('copyExecute').disabled, true);
});
check('no_network_connection_policy', () => {
  assert.match(html, /connect-src 'none'/);
  assert.equal(/\bfetch\s*\(|\bXMLHttpRequest\b|\bWebSocket\b/.test(source), false);
});

const args = process.argv.slice(2);
if (args.length && (args.length !== 2 || args[0] !== '--out')) {
  throw new Error('Usage: node scripts/check_workbench.cjs [--out PATH]');
}
const record = {
  status: 'passed', checked_at_utc: new Date().toISOString(), node_version: process.version,
  executed_argv: [process.execPath, 'scripts/check_workbench.cjs', ...args],
  command: 'node scripts/check_workbench.cjs'+(args.length ? ' --out '+args[1] : ''),
  source: 'web/workbench.html',
  source_sha256: crypto.createHash('sha256').update(html).digest('hex'),
  checker_sha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  checks_passed: checks.length, checks,
  execution: 'Actual inline application JavaScript executed in Node vm with DOM stub',
  browser_visual_qa: 'not performed',
  limitations: ['No browser layout or rendering check', 'No real GIF decoding or download interaction', 'No clipboard API or fallback interaction', 'No network or model request']
};
const output = JSON.stringify(record, null, 2)+'\n';
if (args.length) {
  const target = path.resolve(root, args[1]);
  fs.mkdirSync(path.dirname(target), {recursive: true});
  fs.writeFileSync(target, output);
}
process.stdout.write(output);
