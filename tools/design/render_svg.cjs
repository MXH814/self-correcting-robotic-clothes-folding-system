// Render repository SVG assets. Requires sharp; resolves normal Node/NODE_PATH dependencies.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require('sharp');
async function main() {
  const inputs = process.argv.slice(2);
  if (!inputs.length) throw new Error('Pass one or more .svg paths');
  for (const input of inputs) {
    if (path.extname(input).toLowerCase() !== '.svg') throw new Error('Expected SVG');
    const output = input.replace(/\.svg$/i, '.png');
    await sharp(fs.readFileSync(input), { density: 144 }).png().toFile(output);
    process.stdout.write(output + '\n');
  }
}
main().catch(error => { process.stderr.write(String(error) + '\n'); process.exitCode = 1; });
