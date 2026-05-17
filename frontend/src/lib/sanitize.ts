/**
 * XSS-prevention utilities.
 * Uses the browser's own DOMParser as the sanitizer — no external dependency.
 * Parsing never executes scripts; we then walk the result with an allowlist.
 */

const ALLOWED_TAGS = new Set([
  'p', 'br', 'b', 'strong', 'em', 'i', 'u',
  'ul', 'ol', 'li', 'span', 'div', 'pre', 'code',
])

// Block attributes that can run scripts or change navigation
const DANGEROUS_ATTR = /^(on|formaction$|action$|xlink)/i
const DANGEROUS_PROTO = /^(javascript|data|vbscript):/i

function walkAndClean(src: ChildNode, dest: Node): void {
  for (const child of Array.from(src.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      dest.appendChild(document.createTextNode(child.textContent ?? ''))
      continue
    }
    if (child.nodeType !== Node.ELEMENT_NODE) continue

    const el  = child as Element
    const tag = el.tagName.toLowerCase()

    if (!ALLOWED_TAGS.has(tag)) {
      // Disallowed element — still recurse children (flatten the content)
      walkAndClean(child, dest)
      continue
    }

    const safe = document.createElement(tag)

    for (const { name, value } of Array.from(el.attributes)) {
      if (DANGEROUS_ATTR.test(name)) continue
      if ((name === 'href' || name === 'src') && DANGEROUS_PROTO.test(value.trim())) continue
      safe.setAttribute(name, value)
    }

    walkAndClean(child, safe)
    dest.appendChild(safe)
  }
}

/** Strip unsafe HTML; preserve an allowlisted subset of safe tags and attributes. */
export function sanitizeHtml(dirty: string): string {
  const doc  = new DOMParser().parseFromString(dirty, 'text/html')
  const root = document.createElement('div')
  walkAndClean(doc.body, root)
  return root.innerHTML
}

/** HTML-encode all input — returns plain text safe for any rendering context. */
export function sanitizeText(input: string): string {
  const el = document.createElement('span')
  el.textContent = input
  return el.innerHTML
}

/**
 * Sanitize a filename for use in Content-Disposition / FormData.
 * Removes path separators, null bytes, traversal sequences, and control chars.
 */
export function sanitizeFilename(name: string): string {
  return (
    name
      .replace(/\0/g, '')              // null bytes
      .replace(/[/\\]/g, '_')          // path separators
      .replace(/\.\./g, '.')           // path traversal
      .replace(/[<>:"|?*]/g, '_')      // OS-illegal chars
      .replace(/[\x00-\x1f\x7f]/g, '') // control characters
      .slice(0, 255)
      .trim() || 'upload'
  )
}

/**
 * Sanitize a free-text search query: strip tags and cap length.
 * Safe to interpolate into query params without further encoding.
 */
export function sanitizeSearchQuery(q: string): string {
  return q.replace(/<[^>]*>/g, '').slice(0, 200).trim()
}
