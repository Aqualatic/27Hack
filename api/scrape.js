import { createClient } from '@supabase/supabase-js'

const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

// Helper: check whether a title actually appears in the page text (anti-hallucination)
function isTitleInText(title, text) {
  if (!title || !text) return false
  const normalize = (s) => s.toLowerCase().replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim()
  const t = normalize(title)
  const txt = normalize(text)

  // Exact match
  if (txt.includes(t)) return true

  // Word-based fallback for slight rephrasing
  const titleWords = t.split(' ').filter((w) => w.length > 2)
  if (titleWords.length === 0) return false
  const matched = titleWords.filter((w) => txt.includes(w)).length
  return matched / titleWords.length >= 0.6
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  if (!process.env.GROQ_API_KEY) {
    return res.status(500).json({ error: 'GROQ_API_KEY is not configured in Vercel environment variables.' })
  }
  if (!process.env.VITE_SUPABASE_URL || !process.env.SUPABASE_SERVICE_KEY) {
    return res.status(500).json({ error: 'Supabase credentials are not configured. Need VITE_SUPABASE_URL and SUPABASE_SERVICE_KEY.' })
  }

  const { url } = req.body

  if (!url) {
    return res.status(400).json({ error: 'URL is required' })
  }

  // Force lambda isolation to prevent context leakage between requests
  res.setHeader('Cache-Control', 'no-store, max-age=0, must-revalidate')
  res.setHeader('Vercel-CDN-Cache-Control', 'no-store')
  res.setHeader('Pragma', 'no-cache')
  res.setHeader('Expires', '0')

  // AI will auto-detect all fields. No hints, no fallbacks.
  const validColleges = ['canada', 'csm', 'skyline']
  const validCategories = ['internship', 'scholarship', 'club', 'event', 'other']

  try {
    // Step 1: Fetch via Jina reader (handles JS-rendered pages)
    let pageText
    try {
      const jinaUrl = `https://r.jina.ai/${url}`
      const pageRes = await fetch(jinaUrl, {
        headers: { 'Accept': 'text/plain' },
        signal: AbortSignal.timeout(25000),
      })
      if (!pageRes.ok) {
        return res.status(400).json({ error: `Could not fetch that page (HTTP ${pageRes.status}). Try a different URL.` })
      }
      pageText = await pageRes.text()
    } catch (fetchErr) {
      return res.status(400).json({ error: `Could not reach that URL: ${fetchErr.message}` })
    }

    const stripped = pageText.trim().slice(0, 6000)

    // Step 2: Call Groq - AI auto-detects college and category from page content
    const groqRes = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.GROQ_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'llama-3.1-8b-instant',
        temperature: 0.1,
        max_tokens: 2000,
        stream: false,
        messages: [
          {
            role: 'system',
            content: `You are a strict data extractor for a student resource directory at SMCCD community colleges (Cañada College, College of San Mateo, Skyline College).
Extract resource info from the page text and return ONLY valid JSON — no explanation, no markdown fences, nothing else.

STRICT RULES — FOLLOW EXACTLY:
- Extract ONLY resources that are explicitly mentioned in the provided page text.
- NEVER invent, hallucinate, or infer resources that are not literally present in the text.
- NEVER use information from other pages, previous requests, or your training data.
- Use exact titles and organization names as they appear in the text. Do not rephrase.
- If you cannot find something, set it to null. Do not guess.
- Do NOT use any external knowledge or hints.

Use this schema for each resource:
{
  "title": "exact name of the resource as it appears on the page",
  "organization": "exact name of who offers it, as it appears on the page",
  "deadline": "YYYY-MM-DD or null",
  "description": "2-3 sentences about what this is and who it helps, based ONLY on the page text",
  "type": "internship | scholarship | club | event | other",
  "college": "canada | csm | skyline (use csm if it applies to all colleges, is district-wide, or is unclear)",
  "apply_url": "direct application URL or source URL"
}

Rules for college detection:
- If the page mentions "Cañada" or "Canada College", use "canada"
- If the page mentions "College of San Mateo" or "CSM", use "csm"  
- If the page mentions "Skyline College", use "skyline"
- If the page mentions multiple colleges or is about SMCCD district-wide resources, use "csm"
- If unclear, use "csm" as the default

Rules for type detection:
- internship: Work experience, co-op, paid/unpaid positions
- scholarship: Financial aid, grants, funding for education
- club: Student organizations, recurring meetings, groups
- event: One-time occurrences, workshops, info sessions, deadlines for specific dates
- other: General resources, services, or unclear categories

Date filtering rules:
- If a deadline is in the past (before today's date), set deadline to null
- If no deadline is mentioned, set deadline to null
- Only include future deadlines

Special handling for job boards (Indeed, LinkedIn, etc.):
- Extract individual job postings if listed
- For job listings, use "internship" as the type
- Extract company name as organization
- Extract job title as title
- If no specific deadline, set to null

If the page lists multiple resources return a JSON array of the above.
If you cannot find specific resources return ONE entry with the page heading or site name as the title, and a brief factual description of what the page contains.
Always return valid JSON. Never return plain text.`,
          },
          {
            role: 'user',
            content: `Source URL: ${url}\n\nPage content:\n${stripped}`,
          },
        ],
      }),
    })

    if (!groqRes.ok) {
      const groqErr = await groqRes.text()
      return res.status(500).json({ error: `Groq API error: ${groqErr}` })
    }

    const groqData = await groqRes.json()
    const rawJson = groqData.choices[0].message.content.trim()

    // Step 3: Parse JSON with multiple fallbacks
    let extracted = null

    const attempts = [
      rawJson,
      rawJson.replace(/```json|```/g, '').trim(),
      '[' + rawJson.replace(/```json|```/g, '').trim() + ']',
    ]

    for (const attempt of attempts) {
      try {
        extracted = JSON.parse(attempt)
        break
      } catch {
        continue
      }
    }

    if (!extracted) {
      const match = rawJson.match(/(\[[\s\S]*\]|\{[\s\S]*\})/s)
      if (match) {
        try { extracted = JSON.parse(match[0]) } catch {
          try { extracted = JSON.parse('[' + match[0] + ']') } catch { extracted = null }
        }
      }
    }

    if (!extracted) {
      extracted = {
        title: url.split('/').filter(Boolean).pop().replace(/-/g, ' ') || 'Resource',
        organization: new URL(url).hostname.replace('www.', ''),
        deadline: null,
        description: 'Resource found at ' + url,
        type: 'other',
        apply_url: url,
      }
    }

    // Step 4: Normalize and validate
    const items = Array.isArray(extracted) ? extracted : [extracted]
    let validItems = items.filter(item => item && item.title)

    // Anti-hallucination: replace any item whose title does not appear in the page text
    validItems = validItems.map((item) => {
      if (isTitleInText(item.title, stripped)) {
        return item
      }
      console.warn('Hallucinated title detected, replacing with fallback:', item.title)
      return {
        title: url.split('/').filter(Boolean).pop().replace(/-/g, ' ') || 'Resource',
        organization: new URL(url).hostname.replace('www.', ''),
        deadline: null,
        description: 'Resource found at ' + url,
        type: 'other',
        apply_url: url,
      }
    })

    if (validItems.length === 0) {
      return res.status(400).json({ error: 'Could not extract any resources from that page. Try a different URL.' })
    }

    const now = new Date().toISOString()
    const today = new Date().toISOString().split('T')[0] // YYYY-MM-DD format
    
    const enriched = validItems.map((item) => {
      let detectedCollege = (item.college || 'csm').toString().toLowerCase().trim()

      // Normalize full names and variations to short codes
      if (detectedCollege.includes('cañada') || detectedCollege.includes('canada college')) {
        detectedCollege = 'canada'
      } else if (detectedCollege.includes('college of san mateo')) {
        detectedCollege = 'csm'
      } else if (detectedCollege.includes('skyline')) {
        detectedCollege = 'skyline'
      } else if (detectedCollege.includes('smccd') || detectedCollege.includes('district')) {
        detectedCollege = 'csm'
      }

      if (!validColleges.includes(detectedCollege)) {
        detectedCollege = 'csm'
      }

      let detectedType = item.type || 'other'
      if (!validCategories.includes(detectedType)) {
        detectedType = 'other'
      }

      // Filter out past deadlines - only keep future or null deadlines
      let filteredDeadline = null
      if (item.deadline && item.deadline.match(/^\d{4}-\d{2}-\d{2}$/)) {
        if (item.deadline >= today) {
          filteredDeadline = item.deadline
        }
      }

      return {
        title: item.title || 'Untitled Resource',
        organization: item.organization || null,
        deadline: filteredDeadline,
        description: item.description || null,
        type: detectedType,
        college: detectedCollege,
        category: detectedType,
        source_url: url,
        apply_url: item.apply_url || url,
        scraped_at: now,
      }
    })

    // Step 5: Insert into Supabase
    const supabase = createClient(
      process.env.VITE_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_KEY
    )

    const { data: inserted, error: dbError } = await supabase
      .from('resources')
      .insert(enriched)
      .select()

    if (dbError) {
      return res.status(500).json({ error: `Database error: ${dbError.message}` })
    }

    return res.status(200).json({ success: true, data: inserted })

  } catch (err) {
    console.error('Scrape handler error:', err)
    return res.status(500).json({ error: err.message })
  }
}