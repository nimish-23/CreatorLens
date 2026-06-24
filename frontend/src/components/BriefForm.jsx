import { useState } from "react"

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000") + "/api"

const CAMPAIGN_GOALS = [
  { value: "awareness", label: "AWARENESS" },
  { value: "conversion", label: "CONVERSION" },
  { value: "engagement", label: "ENGAGEMENT" },
  { value: "lead_generation", label: "LEAD GEN" },
]

const FOLLOWER_TIERS = [
  { value: "nano",  label: "NANO",  sub: "1K – 10K" },
  { value: "micro", label: "MICRO", sub: "10K – 100K" },
  { value: "mid",   label: "MID",   sub: "100K – 500K" },
  { value: "macro", label: "MACRO", sub: "500K – 2M" },
  { value: "mega",  label: "MEGA",  sub: "2M+" },
]

const PLATFORMS = ["youtube", "instagram", "twitter"]

export default function BriefForm({ onSubmit }) {
  const [form, setForm] = useState({
    brand_name: "",
    product_description: "",
    campaign_goal: "awareness",
    niche: "",
    platforms: ["youtube"],
    follower_tier: "micro",
    target_audience: "",
    audience_location: "",
    audience_age_range: "",
    language: "English",
    competitor_brands: [],
    budget_inr: "",
    excluded_niches: [],
    additional_context: "",
  })

  const [competitorInput, setCompetitorInput] = useState("")
  const [excludedInput, setExcludedInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const togglePlatform = (p) => {
    setForm((f) => ({
      ...f,
      platforms: f.platforms.includes(p)
        ? f.platforms.filter((x) => x !== p)
        : [...f.platforms, p],
    }))
  }

  const addCompetitor = () => {
    const val = competitorInput.trim()
    if (val && !form.competitor_brands.includes(val)) {
      setForm((f) => ({ ...f, competitor_brands: [...f.competitor_brands, val] }))
      setCompetitorInput("")
    }
  }

  const removeCompetitor = (brand) => {
    setForm((f) => ({ ...f, competitor_brands: f.competitor_brands.filter((b) => b !== brand) }))
  }

  const addExcluded = () => {
    const val = excludedInput.trim()
    if (val && !form.excluded_niches.includes(val)) {
      setForm((f) => ({ ...f, excluded_niches: [...f.excluded_niches, val] }))
      setExcludedInput("")
    }
  }

  const removeExcluded = (niche) => {
    setForm((f) => ({ ...f, excluded_niches: f.excluded_niches.filter((n) => n !== niche) }))
  }

  const handleSubmit = async () => {
    if (
      !form.brand_name ||
      !form.product_description ||
      !form.niche ||
      !form.target_audience ||
      !form.audience_location ||
      !form.audience_age_range ||
      form.platforms.length === 0
    ) {
      setError("Fill in all required fields.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const payload = {
        ...form,
        budget_inr: form.budget_inr ? parseInt(form.budget_inr) : null,
        additional_context: form.additional_context || null,
      }
      const resp = await fetch(`${API}/run-campaign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const data = await resp.json()
      if (data.job_id) {
        onSubmit(data.job_id, form)
      } else {
        setError("Unexpected response from server.")
      }
    } catch (e) {
      setError(`Connection error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="brief-form">
      <div className="form-header">
        <div className="form-eyebrow">NEW CAMPAIGN BRIEF</div>
        <h1 className="form-title">
          Find the right influencer.<br />
          <span>Verify them. Know what to pay.</span>
        </h1>
        <p className="form-subtitle">
          Submit a brief and CreatorLens will discover, audit, and rank influencers using parallel AI agents.
        </p>
      </div>

      <div className="form-grid">
        {/* Brand Name */}
        <div className="form-row">
          <div className="form-field">
            <div className="field-label">BRAND NAME *</div>
            <input
              id="brand-name"
              placeholder="e.g. Mamaearth, Notion, Gymshark"
              value={form.brand_name}
              onChange={(e) => setForm({ ...form, brand_name: e.target.value })}
            />
          </div>
          <div className="form-field">
            <div className="field-label">NICHE *</div>
            <input
              id="niche"
              placeholder="e.g. skincare, productivity, fitness"
              value={form.niche}
              onChange={(e) => setForm({ ...form, niche: e.target.value })}
            />
          </div>
        </div>

        {/* Product Description */}
        <div className="form-row full">
          <div className="form-field">
            <div className="field-label">PRODUCT DESCRIPTION *</div>
            <textarea
              id="product-description"
              placeholder="What is the product and what does it do? 2-4 sentences."
              value={form.product_description}
              onChange={(e) => setForm({ ...form, product_description: e.target.value })}
              rows={3}
              style={{ resize: "vertical", minHeight: 60 }}
            />
          </div>
        </div>

        {/* Campaign Goal + Follower Tier */}
        <div className="form-row">
          <div className="form-field">
            <div className="field-label">CAMPAIGN GOAL *</div>
            <div className="platform-row">
              {CAMPAIGN_GOALS.map((g) => (
                <button
                  key={g.value}
                  className={`platform-btn ${form.campaign_goal === g.value ? "active" : ""}`}
                  onClick={() => setForm({ ...form, campaign_goal: g.value })}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>
          <div className="form-field">
            <div className="field-label">CREATOR SIZE *</div>
            <div className="platform-row">
              {FOLLOWER_TIERS.map((t) => (
                <button
                  key={t.value}
                  className={`platform-btn ${form.follower_tier === t.value ? "active" : ""}`}
                  onClick={() => setForm({ ...form, follower_tier: t.value })}
                  title={t.sub}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Target Audience */}
        <div className="form-row full">
          <div className="form-field">
            <div className="field-label">TARGET AUDIENCE *</div>
            <input
              id="target-audience"
              placeholder="e.g. Indian women 22-35 interested in clean beauty"
              value={form.target_audience}
              onChange={(e) => setForm({ ...form, target_audience: e.target.value })}
            />
          </div>
        </div>

        {/* Location + Age Range + Language */}
        <div className="form-row triple">
          <div className="form-field">
            <div className="field-label">AUDIENCE LOCATION *</div>
            <input
              id="audience-location"
              placeholder="e.g. India, United States"
              value={form.audience_location}
              onChange={(e) => setForm({ ...form, audience_location: e.target.value })}
            />
          </div>
          <div className="form-field">
            <div className="field-label">AGE RANGE *</div>
            <input
              id="audience-age-range"
              placeholder="e.g. 18-35"
              value={form.audience_age_range}
              onChange={(e) => setForm({ ...form, audience_age_range: e.target.value })}
            />
          </div>
          <div className="form-field">
            <div className="field-label">LANGUAGE</div>
            <input
              id="language"
              placeholder="English"
              value={form.language}
              onChange={(e) => setForm({ ...form, language: e.target.value })}
            />
          </div>
        </div>

        {/* Platforms + Budget */}
        <div className="form-row">
          <div className="form-field">
            <div className="field-label">PLATFORMS *</div>
            <div className="platform-row">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  className={`platform-btn ${form.platforms.includes(p) ? "active" : ""}`}
                  onClick={() => togglePlatform(p)}
                >
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="form-field">
            <div className="field-label">BUDGET (INR, optional)</div>
            <input
              id="budget-inr"
              placeholder="e.g. 500000"
              value={form.budget_inr}
              onChange={(e) => setForm({ ...form, budget_inr: e.target.value })}
              type="number"
            />
          </div>
        </div>

        {/* Competitor Brands */}
        <div className="form-row full">
          <div className="form-field">
            <div className="field-label">COMPETITOR BRANDS (optional)</div>
            <div className="keywords-input-row">
              <input
                id="competitor-brands"
                placeholder="add competitor and press +"
                value={competitorInput}
                onChange={(e) => setCompetitorInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCompetitor()}
              />
              <button className="keyword-add-btn" onClick={addCompetitor}>+</button>
            </div>
            {form.competitor_brands.length > 0 && (
              <div className="keyword-tags">
                {form.competitor_brands.map((brand) => (
                  <span key={brand} className="keyword-tag">
                    {brand}
                    <button onClick={() => removeCompetitor(brand)}>×</button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Excluded Niches */}
        <div className="form-row full">
          <div className="form-field">
            <div className="field-label">EXCLUDED NICHES (optional)</div>
            <div className="keywords-input-row">
              <input
                id="excluded-niches"
                placeholder="e.g. adult content, gambling"
                value={excludedInput}
                onChange={(e) => setExcludedInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addExcluded()}
              />
              <button className="keyword-add-btn" onClick={addExcluded}>+</button>
            </div>
            {form.excluded_niches.length > 0 && (
              <div className="keyword-tags">
                {form.excluded_niches.map((niche) => (
                  <span key={niche} className="keyword-tag">
                    {niche}
                    <button onClick={() => removeExcluded(niche)}>×</button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Additional Context */}
        <div className="form-row full">
          <div className="form-field">
            <div className="field-label">ADDITIONAL CONTEXT (optional)</div>
            <textarea
              id="additional-context"
              placeholder="Any other notes — e.g. 'prefer creators who already use our product category'"
              value={form.additional_context}
              onChange={(e) => setForm({ ...form, additional_context: e.target.value })}
              rows={2}
              style={{ resize: "vertical", minHeight: 48 }}
            />
          </div>
        </div>
      </div>

      {error && (
        <div style={{ marginTop: 12, fontSize: 11, color: "var(--red)" }}>
          ✗ {error}
        </div>
      )}

      <div className="form-actions">
        <button className="submit-btn" onClick={handleSubmit} disabled={loading}>
          {loading ? "LAUNCHING..." : "LAUNCH CAMPAIGN →"}
        </button>
        <span className="form-note">~2 min · parallel agents · AI scoring</span>
      </div>
    </div>
  )
}