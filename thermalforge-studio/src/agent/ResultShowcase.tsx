import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

interface ShowcaseItem {
  id: string
  kind: 'image' | 'video'
  src: string
  title: string
  caption: string
  alt?: string
}

const SHOWCASE_ITEMS: ShowcaseItem[] = [
  {
    id: 'prototype-photo',
    kind: 'image',
    src: '/showcase/prototype-photo.jpg',
    title: '样机实物',
    caption: '热增强外壳样机装配实拍',
    alt: '机器人关节热增强外壳样机实物照片',
  },
  {
    id: 'prototype-demo',
    kind: 'video',
    src: '/showcase/prototype-demo.mp4',
    title: '装配演示',
    caption: '外壳拆装与散热验证演示',
  },
]

export function ResultShowcase() {
  const [expanded, setExpanded] = useState(true)

  return (
    <section
      className="result-showcase"
      aria-label="成果展示"
      data-expanded={expanded}
    >
      <header className="result-showcase-header">
        <div>
          <span className="eyebrow">DELIVERABLES</span>
          <h2>成果展示</h2>
        </div>
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={expanded ? '收起成果展示' : '展开成果展示'}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? (
            <ChevronUp aria-hidden="true" />
          ) : (
            <ChevronDown aria-hidden="true" />
          )}
        </button>
      </header>

      {expanded ? (
        <div className="result-showcase-body">
          {SHOWCASE_ITEMS.map((item) => (
            <figure className="result-showcase-item" key={item.id}>
              {item.kind === 'image' ? (
                <a href={item.src} target="_blank" rel="noreferrer">
                  <img src={item.src} alt={item.alt ?? item.title} loading="lazy" />
                </a>
              ) : (
                <video
                  src={item.src}
                  controls
                  preload="metadata"
                  playsInline
                  aria-label={item.title}
                />
              )}
              <figcaption>
                <strong>{item.title}</strong>
                <span>{item.caption}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      ) : null}
    </section>
  )
}
