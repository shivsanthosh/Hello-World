// Strip the document skeleton from the single-file build so it can be published
// as a claude.ai artifact (the host adds its own <html>/<head>/<body>).
import { readFileSync, writeFileSync } from 'node:fs';

const html = readFileSync('dist-artifact/index.html', 'utf8');
const title = html.match(/<title>[\s\S]*?<\/title>/)[0];
const links = (html.match(/<link rel="(?:preconnect|stylesheet)" href="https:\/\/fonts[^>]*>/g) || []).join('\n');
const styles = (html.match(/<style[^>]*>[\s\S]*?<\/style>/g) || []).join('\n');
const scripts = (html.match(/<script[^>]*>[\s\S]*?<\/script>/g) || []).join('\n');
const out = `${title}
<meta name="claude:viewport-fit-sides" content="cover">
${links}
${styles}
<div id="root"></div>
${scripts}
`;
writeFileSync('dist-artifact/artifact.html', out);
console.log(`artifact.html: ${(out.length / 1024).toFixed(0)} KB`);
