// dist/ 의 어느 페이지든 이 사이트 안의 없는 페이지·파일을 가리키면 빌드를 실패시킵니다.
// base 아래의 절대 링크와 상대 링크를 모두 그 링크가 든 페이지 기준으로 풀어 보므로,
// sync-docs.mjs 가 놓친 링크나 특정 base 에서만 통하는 상대 링크가 배포된 사이트의 404 가
// 아니라 여기서 드러납니다. 외부 링크는 요청하지 않습니다.
//
// 번들 자산(/_astro/, /pagefind/)도 건너뛰지 않습니다. 콘텐츠 캐시가 낡으면 캐시된 페이지가
// 이전 빌드의 스타일시트 해시를 가리켜, 링크는 멀쩡한데 코드 블록만 스타일 없이 나옵니다 —
// `astro build --force`(package.json) 가 그 캐시를 비우고, 이 검사가 재발을 잡습니다.
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIST = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist");
const BASE = (process.env.SITE_BASE ?? "/").replace(/\/$/, "");
const ORIGIN = "https://site.invalid";

async function* html(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* html(full);
    else if (entry.name.endsWith(".html")) yield full;
  }
}

async function exists(pathname) {
  if (!pathname.startsWith(`${BASE}/`) && pathname !== `${BASE}/`) return false;
  const rel = decodeURIComponent(pathname.slice(BASE.length)).replace(/^\//, "");
  for (const candidate of [rel, path.join(rel, "index.html")]) {
    try {
      if ((await stat(path.join(DIST, candidate))).isFile()) return true;
    } catch {}
  }
  return false;
}

const broken = [];
let checked = 0;
for await (const file of html(DIST)) {
  const rel = path.relative(DIST, file).split(path.sep).join("/");
  const pageDir = rel.endsWith("index.html") ? rel.slice(0, -"index.html".length) : rel;
  const pageUrl = new URL(`${BASE}/${pageDir}`, ORIGIN);
  const text = await readFile(file, "utf8");
  for (const [, raw] of text.matchAll(/(?:href|src|srcset)="([^"]+)"/g)) {
    const target = raw.split(/\s+/)[0];
    if (/^(#|mailto:|data:|javascript:)/.test(target)) continue;
    const url = new URL(target, pageUrl);
    if (url.origin !== ORIGIN) continue;
    checked++;
    if (!(await exists(url.pathname))) broken.push(`${rel}: ${target}`);
  }
}
for (const b of broken) console.error(`broken link ${b}`);
console.log(`checked ${checked} internal links under base "${BASE || "/"}", ${broken.length} broken`);
process.exit(broken.length ? 1 : 0);
