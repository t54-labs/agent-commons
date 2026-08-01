import PF from "pathfinding";
import { navigationPathIsWalkable, pointInPolygon, pointIsWalkable, VILLAGE_LEVEL, type MapPoint } from "./villageLevel";

const CELL_SIZE = VILLAGE_LEVEL.navigation.cellSize;
const GRID_WIDTH = Math.ceil(VILLAGE_LEVEL.map.width / CELL_SIZE);
const GRID_HEIGHT = Math.ceil(VILLAGE_LEVEL.map.height / CELL_SIZE);
const AGENT_RADIUS = 8;
const DESTINATION_ATTEMPTS = 48;
const RECENT_DESTINATION_LIMIT = 6;

export type RandomPathState = {
  randomState: number;
  recentDestinationKeys: string[];
  destinationCount: number;
};

export type RandomPathPlan = RandomPathState & {
  points: MapPoint[];
  destinationKey: string;
};

type GridPoint = { x: number; y: number };

export type StationExitDiagnostic = {
  stationId: string;
  transitionCount: number;
  unauthorizedTransitionCount: number;
  maxPortalDistance: number;
};

function nextRandom(state: number): { state: number; value: number } {
  const next = ((state || 0x9e3779b9) + 0x6d2b79f5) >>> 0;
  let mixed = next;
  mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
  mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
  mixed = (mixed ^ (mixed >>> 14)) >>> 0;
  return { state: next, value: mixed / 0x1_0000_0000 };
}

function cellCenter(cell: GridPoint): MapPoint {
  return {
    x: Math.min(VILLAGE_LEVEL.map.width - 1, cell.x * CELL_SIZE + CELL_SIZE / 2),
    y: Math.min(VILLAGE_LEVEL.map.height - 1, cell.y * CELL_SIZE + CELL_SIZE / 2),
  };
}

function pointToCell(point: MapPoint): GridPoint {
  return {
    x: Math.max(0, Math.min(GRID_WIDTH - 1, Math.floor(point.x / CELL_SIZE))),
    y: Math.max(0, Math.min(GRID_HEIGHT - 1, Math.floor(point.y / CELL_SIZE))),
  };
}

function cellKey(cell: GridPoint): string {
  return `${cell.x}:${cell.y}`;
}

function createNavigationMatrix(): number[][] {
  return Array.from({ length: GRID_HEIGHT }, (_, y) => (
    Array.from({ length: GRID_WIDTH }, (_, x) => pointIsWalkable(cellCenter({ x, y }), AGENT_RADIUS) ? 0 : 1)
  ));
}

const NAVIGATION_MATRIX = createNavigationMatrix();
const WALKABLE_CELLS = NAVIGATION_MATRIX.flatMap((row, y) => (
  row.flatMap((value, x) => value === 0 ? [{ x, y }] : [])
));

type NavigationComponent = {
  size: number;
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
  };
};

function navigationComponents(): NavigationComponent[] {
  const visited = new Set<string>();
  const components: NavigationComponent[] = [];
  WALKABLE_CELLS.forEach((origin) => {
    if (visited.has(cellKey(origin))) return;
    const queue = [origin];
    visited.add(cellKey(origin));
    let size = 0;
    const bounds = { minX: origin.x, minY: origin.y, maxX: origin.x, maxY: origin.y };
    while (queue.length) {
      const current = queue.shift()!;
      size += 1;
      bounds.minX = Math.min(bounds.minX, current.x);
      bounds.minY = Math.min(bounds.minY, current.y);
      bounds.maxX = Math.max(bounds.maxX, current.x);
      bounds.maxY = Math.max(bounds.maxY, current.y);
      for (const [offsetX, offsetY] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const next = { x: current.x + offsetX, y: current.y + offsetY };
        if (next.x < 0 || next.y < 0 || next.x >= GRID_WIDTH || next.y >= GRID_HEIGHT) continue;
        const key = cellKey(next);
        if (visited.has(key) || NAVIGATION_MATRIX[next.y][next.x] !== 0) continue;
        visited.add(key);
        queue.push(next);
      }
    }
    components.push({
      size,
      bounds: {
        minX: bounds.minX * CELL_SIZE,
        minY: bounds.minY * CELL_SIZE,
        maxX: (bounds.maxX + 1) * CELL_SIZE,
        maxY: (bounds.maxY + 1) * CELL_SIZE,
      },
    });
  });
  return components.sort((left, right) => right.size - left.size);
}

const NAVIGATION_COMPONENTS = navigationComponents();

function gridFromMatrix(): PF.Grid {
  return new PF.Grid(NAVIGATION_MATRIX.map((row) => [...row]));
}

function nearestWalkableCell(point: MapPoint): GridPoint | null {
  const origin = pointToCell(point);
  if (NAVIGATION_MATRIX[origin.y]?.[origin.x] === 0) return origin;
  const maxRadius = Math.max(GRID_WIDTH, GRID_HEIGHT);
  for (let radius = 1; radius <= maxRadius; radius += 1) {
    for (let y = origin.y - radius; y <= origin.y + radius; y += 1) {
      for (let x = origin.x - radius; x <= origin.x + radius; x += 1) {
        if (x < 0 || y < 0 || x >= GRID_WIDTH || y >= GRID_HEIGHT) continue;
        if (Math.max(Math.abs(x - origin.x), Math.abs(y - origin.y)) !== radius) continue;
        if (NAVIGATION_MATRIX[y][x] === 0) return { x, y };
      }
    }
  }
  return null;
}

function findPath(start: GridPoint, destination: GridPoint): MapPoint[] {
  const grid = gridFromMatrix();
  const finder = new PF.AStarFinder({
    diagonalMovement: PF.DiagonalMovement.OnlyWhenNoObstacles,
    heuristic: PF.Heuristic.octile,
  });
  const rawPath = finder.findPath(start.x, start.y, destination.x, destination.y, grid);
  if (rawPath.length < 2) return [];
  const compressed = PF.Util.compressPath(rawPath);
  const points = compressed.map(([x, y]) => cellCenter({ x, y }));
  return navigationPathIsWalkable(points) ? points : rawPath.map(([x, y]) => cellCenter({ x, y }));
}

function distanceBetween(left: MapPoint, right: MapPoint): number {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function distanceToSegment(point: MapPoint, start: MapPoint, end: MapPoint): number {
  const segmentX = end.x - start.x;
  const segmentY = end.y - start.y;
  const lengthSquared = segmentX * segmentX + segmentY * segmentY;
  if (!lengthSquared) return distanceBetween(point, start);
  const progress = Math.max(0, Math.min(1, (
    (point.x - start.x) * segmentX + (point.y - start.y) * segmentY
  ) / lengthSquared));
  return distanceBetween(point, {
    x: start.x + segmentX * progress,
    y: start.y + segmentY * progress,
  });
}

function pathDistance(points: MapPoint[]): number {
  return points.slice(1).reduce((total, point, index) => total + distanceBetween(points[index], point), 0);
}

export function planPath(from: MapPoint, to: MapPoint): MapPoint[] | null {
  const start = nearestWalkableCell(from);
  const destination = nearestWalkableCell(to);
  if (!start || !destination) return null;
  const points = findPath(start, destination);
  return points.length > 1 ? points : null;
}

export function planRandomPath(from: MapPoint, state: RandomPathState): RandomPathPlan | null {
  const start = nearestWalkableCell(from);
  if (!start || WALKABLE_CELLS.length < 2) return null;

  let randomState = state.randomState;
  const recent = new Set(state.recentDestinationKeys);
  for (let attempt = 0; attempt < DESTINATION_ATTEMPTS; attempt += 1) {
    const random = nextRandom(randomState);
    randomState = random.state;
    const destination = WALKABLE_CELLS[Math.floor(random.value * WALKABLE_CELLS.length)];
    const destinationKey = cellKey(destination);
    if (recent.has(destinationKey)) continue;
    if (distanceBetween(cellCenter(start), cellCenter(destination)) < VILLAGE_LEVEL.navigation.destinationMinDistance) continue;
    const points = findPath(start, destination);
    if (points.length < 2) continue;
    if (pathDistance(points) > VILLAGE_LEVEL.navigation.destinationMaxPathDistance) continue;
    const recentDestinationKeys = [...state.recentDestinationKeys, destinationKey].slice(-RECENT_DESTINATION_LIMIT);
    return {
      points,
      destinationKey,
      randomState,
      recentDestinationKeys,
      destinationCount: state.destinationCount + 1,
    };
  }
  return null;
}

export function stationExitDiagnostics(maxPortalDistance = CELL_SIZE * 4): StationExitDiagnostic[] {
  return VILLAGE_LEVEL.stations.map((station, stationIndex) => {
    const roomPolygon = VILLAGE_LEVEL.navigation.walkablePolygons[stationIndex];
    const portal = VILLAGE_LEVEL.portals.find((candidate) => candidate.stationId === station.id)!;
    const transitions: MapPoint[] = [];
    WALKABLE_CELLS.forEach((cell) => {
      const center = cellCenter(cell);
      if (!pointInPolygon(center, roomPolygon)) return;
      for (const [offsetX, offsetY] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const neighbor = { x: cell.x + offsetX, y: cell.y + offsetY };
        if (neighbor.x < 0 || neighbor.y < 0 || neighbor.x >= GRID_WIDTH || neighbor.y >= GRID_HEIGHT) continue;
        if (NAVIGATION_MATRIX[neighbor.y][neighbor.x] !== 0) continue;
        const neighborCenter = cellCenter(neighbor);
        if (pointInPolygon(neighborCenter, roomPolygon)) continue;
        transitions.push({
          x: (center.x + neighborCenter.x) / 2,
          y: (center.y + neighborCenter.y) / 2,
        });
      }
    });
    const distances = transitions.map((point) => distanceToSegment(point, portal.inside, portal.outside));
    return {
      stationId: station.id,
      transitionCount: transitions.length,
      unauthorizedTransitionCount: distances.filter((distance) => distance > maxPortalDistance).length,
      maxPortalDistance: Math.max(0, ...distances),
    };
  });
}

export function navigationDiagnostics(): {
  cellSize: number;
  gridWidth: number;
  gridHeight: number;
  walkableCellCount: number;
  componentCount: number;
  largestComponentSize: number;
  components: NavigationComponent[];
} {
  return {
    cellSize: CELL_SIZE,
    gridWidth: GRID_WIDTH,
    gridHeight: GRID_HEIGHT,
    walkableCellCount: WALKABLE_CELLS.length,
    componentCount: NAVIGATION_COMPONENTS.length,
    largestComponentSize: NAVIGATION_COMPONENTS[0]?.size || 0,
    components: NAVIGATION_COMPONENTS,
  };
}
