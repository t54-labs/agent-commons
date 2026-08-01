import levelSource from "../assets-source/village/level-v3.json";

export type MapPoint = { x: number; y: number };

export type VillageStation = {
  id: string;
  center: MapPoint;
  sign: MapPoint;
  agentSlots: MapPoint[];
  connector: {
    loopIndex: number;
    points: MapPoint[];
  };
};

export type VillageObject = {
  id: string;
  kind: "workstation" | "landscape" | "lamp" | "storage";
  asset: string;
  position: MapPoint;
  depthY: number;
  fadeWhenOccluded: boolean;
  collisionPolygons: MapPoint[][];
};

export type VillageBoundary = {
  id: string;
  collisionPolygons: MapPoint[][];
};

export type VillagePortal = {
  stationId: string;
  inside: MapPoint;
  outside: MapPoint;
};

type PointTuple = [number, number];

function mapPoint([x, y]: PointTuple): MapPoint {
  return { x, y };
}

export const VILLAGE_LEVEL = {
  version: levelSource.version,
  map: levelSource.map,
  navigation: {
    cellSize: levelSource.navigation.cell_size,
    destinationMinDistance: levelSource.navigation.destination_min_distance,
    destinationMaxPathDistance: levelSource.navigation.destination_max_path_distance,
    walkablePolygons: levelSource.navigation.walkable_polygons.map((polygon) => (
      polygon.map((point) => mapPoint(point as PointTuple))
    )),
  },
  centralLoop: levelSource.navigation.central_loop.map((point) => mapPoint(point as PointTuple)),
  stations: levelSource.stations.map((station): VillageStation => ({
    id: station.id,
    center: mapPoint(station.center as PointTuple),
    sign: mapPoint(station.sign as PointTuple),
    agentSlots: station.agent_slots.map((point) => mapPoint(point as PointTuple)),
    connector: {
      loopIndex: station.connector.loop_index,
      points: station.connector.points.map((point) => mapPoint(point as PointTuple)),
    },
  })),
  boundaries: levelSource.boundaries.map((boundary): VillageBoundary => ({
    id: boundary.id,
    collisionPolygons: boundary.collision_polygons.map((polygon) => (
      polygon.map((point) => mapPoint(point as PointTuple))
    )),
  })),
  portals: levelSource.portals.map((portal): VillagePortal => ({
    stationId: portal.station_id,
    inside: mapPoint(portal.inside as PointTuple),
    outside: mapPoint(portal.outside as PointTuple),
  })),
  objects: levelSource.objects.map((object): VillageObject => ({
    id: object.id,
    kind: object.kind as VillageObject["kind"],
    asset: object.asset,
    position: mapPoint(object.position as PointTuple),
    depthY: object.depth_y,
    fadeWhenOccluded: object.fade_when_occluded,
    collisionPolygons: object.collision_polygons.map((polygon) => (
      polygon.map((point) => mapPoint(point as PointTuple))
    )),
  })),
} as const;

export function pointInPolygon(point: MapPoint, polygon: MapPoint[]): boolean {
  let inside = false;
  for (let current = 0, previous = polygon.length - 1; current < polygon.length; previous = current, current += 1) {
    const currentPoint = polygon[current];
    const previousPoint = polygon[previous];
    const crosses = (currentPoint.y > point.y) !== (previousPoint.y > point.y)
      && point.x < ((previousPoint.x - currentPoint.x) * (point.y - currentPoint.y))
        / (previousPoint.y - currentPoint.y || Number.EPSILON) + currentPoint.x;
    if (crosses) inside = !inside;
  }
  return inside;
}

export function pointIsInWalkableArea(point: MapPoint): boolean {
  return VILLAGE_LEVEL.navigation.walkablePolygons.some((polygon) => pointInPolygon(point, polygon));
}

export function footPointIsBlocked(point: MapPoint, radius = 0): boolean {
  const samples = radius > 0
    ? [
        point,
        { x: point.x - radius, y: point.y },
        { x: point.x + radius, y: point.y },
        { x: point.x, y: point.y - radius * 0.45 },
        { x: point.x, y: point.y + radius * 0.45 },
      ]
    : [point];
  return [...VILLAGE_LEVEL.objects, ...VILLAGE_LEVEL.boundaries].some((item) => (
    item.collisionPolygons.some((polygon) => samples.some((sample) => pointInPolygon(sample, polygon)))
  ));
}

export function pointIsWalkable(point: MapPoint, radius = 0): boolean {
  return pointIsInWalkableArea(point) && !footPointIsBlocked(point, radius);
}

export function navigationSegmentIsWalkable(start: MapPoint, end: MapPoint, radius = 8): boolean {
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const sampleCount = Math.max(1, Math.ceil(distance / 6));
  for (let index = 0; index <= sampleCount; index += 1) {
    const progress = index / sampleCount;
    if (!pointIsWalkable({
      x: start.x + (end.x - start.x) * progress,
      y: start.y + (end.y - start.y) * progress,
    }, radius)) return false;
  }
  return true;
}

export function navigationPathIsWalkable(path: MapPoint[]): boolean {
  return path.length > 1 && path.slice(0, -1).every((point, index) => navigationSegmentIsWalkable(point, path[index + 1]));
}

export function segmentIsWalkable(start: MapPoint, end: MapPoint, radius = 8): boolean {
  const distance = Math.hypot(end.x - start.x, end.y - start.y);
  const sampleCount = Math.max(1, Math.ceil(distance / 6));
  for (let index = 0; index <= sampleCount; index += 1) {
    const progress = index / sampleCount;
    const point = {
      x: start.x + (end.x - start.x) * progress,
      y: start.y + (end.y - start.y) * progress,
    };
    if (footPointIsBlocked(point, radius)) return false;
  }
  return true;
}

export function pathIsWalkable(path: MapPoint[]): boolean {
  return path.length > 1 && path.slice(0, -1).every((point, index) => segmentIsWalkable(point, path[index + 1]));
}

export function routeIsWalkable(route: MapPoint[]): boolean {
  return pathIsWalkable(route) && segmentIsWalkable(route[route.length - 1], route[0]);
}
