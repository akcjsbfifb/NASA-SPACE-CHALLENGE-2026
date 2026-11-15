#!/usr/bin/env node
import readline from 'node:readline';

const rl = readline.createInterface({ input: process.stdin });
const canned = {
  returned: 2,
  precision: 0.7,
  points: [{ lat: 1.0, lon: 2.0, closeness: 0.9 }],
};

rl.on('line', () => {
  process.stdout.write(`${JSON.stringify(canned)}\n`);
});