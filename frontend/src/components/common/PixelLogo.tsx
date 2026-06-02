interface PixelLogoProps {
  size?: number
}

export default function PixelLogo({ size = 32 }: PixelLogoProps) {
  const s = size / 32
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      style={{ imageRendering: 'pixelated', display: 'block', flexShrink: 0 }}
    >
      {/* Dark pixel outline background */}
      <rect x="1" y="1" width="30" height="30" rx="4" fill="#1B2A3A" />

      {/* Crystal body — blue */}
      <polygon points="16,5 22,12 20,22 12,22 10,12" fill="#5CC8FF" opacity="0.9" />
      {/* Crystal highlight */}
      <polygon points="16,5 19,10 17,10" fill="#A8E6FF" />
      {/* Crystal dark face */}
      <polygon points="12,22 10,12 14,16" fill="#2A8FBF" />

      {/* Graph nodes */}
      <rect x="5" y="18" width="4" height="4" rx="1" fill="#7ACB6A" />
      <rect x="23" y="18" width="4" height="4" rx="1" fill="#7ACB6A" />
      <rect x="14" y="24" width="4" height="4" rx="1" fill="#9A6A3A" />

      {/* Graph edges */}
      <line x1="9" y1="20" x2="14" y2="22" stroke="#7ACB6A" strokeWidth="1.5" />
      <line x1="23" y1="20" x2="18" y2="22" stroke="#7ACB6A" strokeWidth="1.5" />

      {/* Green sprout on top */}
      <rect x="15" y="2" width="2" height="4" fill="#7ACB6A" />
      <rect x="13" y="3" width="2" height="2" fill="#7ACB6A" />
      <rect x="17" y="3" width="2" height="2" fill="#7ACB6A" />

      {/* Pixel outline border */}
      <rect x="1" y="1" width="30" height="30" rx="4" fill="none" stroke="#1B2A3A" strokeWidth="2" />
    </svg>
  )
}
