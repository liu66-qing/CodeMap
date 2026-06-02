import mentor from '../overview/farm-mentor.png'
import woodBoard from '../overview/wood-board.png'
import bridge from '../overview/decor-bridge.png'
import chest from '../overview/decor-chest.png'
import flag from '../overview/decor-flag.png'
import flowers from '../overview/decor-flowers.png'
import grass from '../overview/decor-grass.png'
import sign from '../overview/decor-sign.png'
import stones from '../overview/decor-stones.png'
import stump from '../overview/decor-stump.png'

import badgeClipboard from './badge-clipboard.png'
import badgeMap from './badge-map.png'
import campfireCrates from './campfire-crates.png'
import crystalAgentBlue from './crystal-agent-blue.png'
import crystalLoopGreen from './crystal-loop-green.png'
import crystalMemoryPurple from './crystal-memory-purple.png'
import mentorMiner from './mentor-miner.png'
import mentorRunner from './mentor-runner.png'
import mentorTrophy from './mentor-trophy.png'
import mineEntrance from './mine-entrance.png'
import routeArrowBlue from './route-arrow-blue.png'
import woodArrowSign from './wood-arrow-sign.png'
import journeyMapBg from '../backgrounds/journey-map-bg.png'
import mainflowRoad from '../backgrounds/mainflow-road.png'
import showcaseMine from '../backgrounds/showcase-mine.png'
import takeawayCampfire from '../backgrounds/takeaway-campfire.png'

export const overviewAssets = {
  mentor,
  woodBoard,
  bridge,
  chest,
  flag,
  flowers,
  grass,
  sign,
  stones,
  stump,
} as const

export const stageAssets = {
  mentorRunner,
  mentorMiner,
  mentorTrophy,
  woodArrowSign,
  routeArrowBlue,
  crystalMemoryPurple,
  crystalAgentBlue,
  crystalLoopGreen,
  campfireCrates,
  mineEntrance,
  badgeClipboard,
  badgeMap,
} as const

export const stageBackgrounds = {
  learningMap: journeyMapBg,
  mainflow: mainflowRoad,
  showcase: showcaseMine,
  takeaway: takeawayCampfire,
} as const

export type StageAssetKey = keyof typeof stageAssets
export type StageBackgroundKey = keyof typeof stageBackgrounds
