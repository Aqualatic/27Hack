import { createClient } from '@supabase/supabase-js'

// ─── Detect college from URL ─────────────────────────────────────────────────
function detectCollegeFromUrl(url) {
  const h = new URL(url).hostname.toLowerCase()
  if (h.includes('canadacollege') || h.includes('canada.edu')) return 'canada'
  if (h.includes('collegeofsanmateo') || h.includes('csm.edu')) return 'csm'
  if (h.includes('skylinecollege') || h.includes('skyline.edu')) return 'skyline'
  if (h.includes('smccd')) return 'smccd'
  return null
}

// ─── Repair + parse potentially truncated JSON from Groq ────────────────────
function parseGroqJson(raw) {
  if (!raw) return null

  // Strip code fences
  let s = raw
    .replace(/^```json\s*/i, '')
    .replace(/^```\s*/i, '')
    .replace(/```\s*$/i, '')
    .trim()

  // Find outermost array or object bounds
  const isArray = s.trimStart().startsWith('[')
  const start = isArray ? s.indexOf('[') : s.indexOf('{')
  if (start === -1) return null
  s = s.slice(start)

  // 1. Try parsing as-is first
  try { return JSON.parse(s) } catch {}

  // 2. Truncation repair: strip the last incomplete item and close the structure
  if (isArray) {
    // Remove everything after the last complete object (last },  or }  before end)
    const lastGoodClose = s.lastIndexOf('}')
    if (lastGoodClose !== -1) {
      const repaired = s.slice(0, lastGoodClose + 1) + ']'
      try { return JSON.parse(repaired) } catch {}
    }
  } else {
    const lastGoodClose = s.lastIndexOf('}')
    if (lastGoodClose !== -1) {
      try { return JSON.parse(s.slice(0, lastGoodClose + 1)) } catch {}
    }
  }

  return null
}

// ─── Strip nav/footer noise before sending to Groq ──────────────────────────
const NAV_LINE_RE = [
  /^(home|menu|search|login|log in|sign in|sign up|register|contact us|about|sitemap|skip to|back to top)\b/i,
  /^(facebook|twitter|instagram|youtube|linkedin|tiktok|snapchat)\b/i,
  /^(privacy policy|terms of use|accessibility|copyright|©)/i,
  /^\s*[\|>\\/·•]\s*$/,
  /^\d{1,2}\/\d{1,2}\/\d{2,4}$/,
]

const NAV_HEADINGS = [
  'quick links', 'additional links', 'related links', 'see also',
  'connect with us', 'follow us', 'social media', 'contact us',
  'more information', 'footer', 'navigation', 'breadcrumb',
]

function cleanPage(raw) {
  const lines = raw.split('\n')
  let inNav = false
  const kept = []

  for (const line of lines) {
    const t = line.trim()
    if (!t) { kept.push(''); continue }
    const lower = t.toLowerCase().replace(/[#*_]/g, '').trim()

    if (NAV_HEADINGS.some(kw => lower.includes(kw))) { inNav = true; continue }
    if (/^#{1,3} /.test(t) && !NAV_HEADINGS.some(kw => lower.includes(kw))) inNav = false
    if (inNav) continue
    if (NAV_LINE_RE.some(p => p.test(t))) continue

    kept.push(line)
  }

  return kept.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' })
  if (!process.env.GROQ_API_KEY) return res.status(500).json({ error: 'GROQ_API_KEY not configured' })
  if (!process.env.VITE_SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY)
    return res.status(500).json({ error: 'Supabase credentials not configured' })

  const { url } = req.body
  if (!url) return res.status(400).json({ error: 'URL is required' })

  const urlCollege = detectCollegeFromUrl(url)

  try {
    // ── Step 1: Fetch via Jina ────────────────────────────────────────────
    const pageRes = await fetch(`https://r.jina.ai/${url}`, {
      headers: { Accept: 'text/plain' },
      signal: AbortSignal.timeout(25000),
    })
    if (!pageRes.ok) return res.status(400).json({ error: `Could not fetch page (HTTP ${pageRes.status})` })

    const text = cleanPage(await pageRes.text()).slice(0, 6000)

    // ── Step 2: Groq ──────────────────────────────────────────────────────
    const groqRes = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${process.env.GROQ_API_KEY}` },
      body: JSON.stringify({
        model: 'llama-3.1-8b-instant',
        temperature: 0.1,
        max_tokens: 2500,
        messages: [
          {
            role: 'system',
            content: `Extract real student resources from a community college page. Return ONLY raw JSON — no prose, no markdown fences.

EXTRACT: named clubs/orgs, scholarships, internships, academic support programs (EOPS, DSPS, tutoring, transfer center), campus services (food pantry, health center, CalWORKs), events with real details.

SKIP: nav links, Home/About/Contact/Login, social media, footers, breadcrumbs, staff directories, generic headings with no content, duplicates.

Multiple resources → JSON array. One resource → JSON object. None → {"error":"no_resources"}

Each item: {"title":"exact name","organization":"who runs it","deadline":null,"description":"1 short sentence","type":"club|scholarship|internship|event|other","college":"canada|csm|skyline|smccd","apply_url":"https://..."}

IMPORTANT: Keep descriptions SHORT (1 sentence max) to avoid hitting output limits. title = specific item name not page title. deadline = YYYY-MM-DD only if a real future date is stated, else null.`,
          },
          {
            role: 'user',
            content: `URL: ${url}\n\nPage content:\n${text}`,
          },
        ],
      }),
    })

    if (!groqRes.ok) {
      const errText = await groqRes.text()
      return res.status(500).json({ error: `Groq API error (${groqRes.status}): ${errText}` })
    }

    const groqData = await groqRes.json()
    const choice = groqData.choices?.[0]
    const rawContent = choice?.message?.content?.trim() ?? ''

    console.log('[scrape] finish_reason:', choice?.finish_reason)
    console.log('[scrape] Groq output length:', rawContent.length)
    console.log('[scrape] Groq tail:', rawContent.slice(-200))

    // ── Step 3: Parse (with truncation repair) ────────────────────────────
    const extracted = parseGroqJson(rawContent)

    if (!extracted) {
      console.error('[scrape] Parse failed. Raw:\n', rawContent)
      return res.status(400).json({ error: 'Could not parse AI response.', debug: rawContent.slice(0, 600) })
    }

    if (extracted?.error === 'no_resources') {
      return res.status(400).json({ error: 'No real student resources found on this page.' })
    }

    // ── Step 4: Normalize ─────────────────────────────────────────────────
    const items = Array.isArray(extracted) ? extracted : [extracted]
    const today = new Date().toISOString().split('T')[0]
    const now = new Date().toISOString()
    const VALID_TYPES = ['internship', 'scholarship', 'club', 'event', 'other']
    const VALID_COLLEGES = ['canada', 'csm', 'skyline', 'smccd']

    const enriched = items
      .filter(item => item?.title && typeof item.title === 'string' && item.title.trim().length > 2)
      .map(item => ({
        title: item.title.trim().slice(0, 200),
        organization: item.organization?.trim() || null,
        deadline: item.deadline && item.deadline >= today ? item.deadline : null,
        description: item.description?.trim() || null,
        type: VALID_TYPES.includes(item.type) ? item.type : 'other',
        college: urlCollege || (VALID_COLLEGES.includes(item.college) ? item.college : 'smccd'),
        source_url: url,
        apply_url: item.apply_url || url,
        scraped_at: now,
      }))

    if (enriched.length === 0) {
      return res.status(400).json({ error: 'No valid resources could be extracted from this page.' })
    }

    // ── Step 5: Supabase insert ───────────────────────────────────────────
    const supabase = createClient(process.env.VITE_SUPABASE_URL, process.env.SUPABASE_SERVICE_KEY)
    const { data: inserted, error: dbError } = await supabase.from('resources').insert(enriched).select()

    if (dbError) return res.status(500).json({ error: `Database error: ${dbError.message}` })

    return res.status(200).json({ success: true, data: inserted })

  } catch (err) {
    console.error('[scrape] Unhandled error:', err)
    return res.status(500).json({ error: err.message })
  }
}