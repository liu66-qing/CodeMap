interface PixelMentorProps {
  size?: number
}

/**
 * Pure pixel-art boy mentor — built from CSS-grid-style rect blocks.
 * Each rect = one "pixel" of the sprite. 16x20 grid scaled by `size`.
 */
export default function PixelMentor({ size = 140 }: PixelMentorProps) {
  const W = 16
  const H = 20
  const px = size / W

  // Color palette
  const SKIN = '#ffd9a8'
  const SKIN_DARK = '#e0a878'
  const HAIR = '#5a3a1a'
  const EYE = '#1a1a1a'
  const SHIRT = '#3a8b4f'
  const SHIRT_DARK = '#296a38'
  const PANTS = '#3a5aa0'
  const PANTS_DARK = '#2a4280'
  const BOOT = '#3a2618'
  const MOUTH = '#c8624a'

  // Sprite map: each entry is [x, y, w, h, color]
  const sprite: [number, number, number, number, string][] = [
    // Hair top
    [5, 1, 6, 1, HAIR],
    [4, 2, 8, 1, HAIR],
    [4, 3, 8, 1, HAIR],
    // Face
    [5, 4, 6, 3, SKIN],
    [4, 4, 1, 3, HAIR], // left side hair
    [11, 4, 1, 3, HAIR], // right side hair
    // Eyes
    [6, 5, 1, 1, EYE],
    [9, 5, 1, 1, EYE],
    // Cheek dots
    [5, 6, 1, 1, SKIN_DARK],
    [10, 6, 1, 1, SKIN_DARK],
    // Mouth
    [7, 6, 2, 1, MOUTH],
    // Neck
    [7, 7, 2, 1, SKIN_DARK],
    // Shirt body
    [4, 8, 8, 4, SHIRT],
    [4, 8, 1, 4, SHIRT_DARK],
    [11, 8, 1, 4, SHIRT_DARK],
    // Shirt collar
    [7, 8, 2, 1, SHIRT_DARK],
    // Belt
    [4, 12, 8, 1, BOOT],
    // Arm left (raised waving)
    [2, 7, 2, 1, SKIN],
    [2, 6, 2, 1, SKIN],
    [1, 5, 2, 2, SKIN],
    [1, 4, 1, 1, SKIN_DARK],
    // Arm right (down at side)
    [12, 9, 2, 3, SHIRT],
    [13, 12, 2, 1, SKIN],
    // Legs
    [5, 13, 3, 4, PANTS],
    [8, 13, 3, 4, PANTS],
    [5, 13, 1, 4, PANTS_DARK],
    [10, 13, 1, 4, PANTS_DARK],
    // Boots
    [4, 17, 4, 2, BOOT],
    [8, 17, 4, 2, BOOT],
    // Ground shadow
    [3, 19, 10, 1, '#3a2a1a'],
  ]

  return (
    <svg
      width={size}
      height={(size * H) / W}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        imageRendering: 'pixelated',
        display: 'block',
        filter: 'drop-shadow(2px 3px 0 rgba(15, 23, 42, 0.25))',
      }}
      aria-label="像素导师"
    >
      {sprite.map(([x, y, w, h, color], i) => (
        <rect key={i} x={x} y={y} width={w} height={h} fill={color} shapeRendering="crispEdges" />
      ))}
      <style>{`
        @keyframes mentor-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-${px * 0.15}px); } }
      `}</style>
    </svg>
  )
}
