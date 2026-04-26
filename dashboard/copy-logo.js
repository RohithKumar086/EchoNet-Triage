// Quick script to copy the logo to the public folder
// Run: node copy-logo.js
const fs = require('fs');
const path = require('path');

const src = path.join(
  process.env.USERPROFILE || process.env.HOME,
  '.gemini', 'antigravity', 'brain',
  '376c10a3-a8bc-484a-bc06-70f46df1668a',
  'media__1777202386196.jpg'
);
const dest = path.join(__dirname, 'public', 'logo.png');

try {
  fs.copyFileSync(src, dest);
  console.log('✅ Logo copied to', dest);
} catch (e) {
  console.error('❌ Failed:', e.message);
  console.log('\nManual fallback: copy your logo image to:');
  console.log(dest);
}
