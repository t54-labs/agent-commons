import { describe, expect, test } from "vitest";
import { footPointIsBlocked, navigationPathIsWalkable, navigationSegmentIsWalkable, pointIsWalkable, VILLAGE_LEVEL, type MapPoint } from "./villageLevel";
import { navigationDiagnostics, planPath, planRandomPath, stationExitDiagnostics, type RandomPathPlan, type RandomPathState } from "./villageNavigation";


function initialState(seed: number): RandomPathState {
  return { randomState: seed, recentDestinationKeys: [], destinationCount: 0 };
}

function destination(plan: RandomPathPlan): MapPoint {
  return plan.points[plan.points.length - 1];
}

function routeDistance(points: MapPoint[]): number {
  return points.slice(1).reduce((total, point, index) => (
    total + Math.hypot(point.x - points[index].x, point.y - points[index].y)
  ), 0);
}

describe("village random navigation", () => {
  test("builds a substantial navigation grid", () => {
    const diagnostics = navigationDiagnostics();
    expect(diagnostics.cellSize).toBe(16);
    expect(diagnostics.walkableCellCount).toBeGreaterThan(1_000);
    expect(diagnostics.componentCount, JSON.stringify(diagnostics.components)).toBe(1);
    expect(diagnostics.largestComponentSize).toBe(diagnostics.walkableCellCount);
  });

  test("replays the same destination and path for the same seed", () => {
    const start = VILLAGE_LEVEL.stations[0].agentSlots[0];
    const first = planRandomPath(start, initialState(0x1234abcd));
    const replay = planRandomPath(start, initialState(0x1234abcd));
    expect(first).not.toBeNull();
    expect(replay).toEqual(first);
  });

  test("plans collision-free paths from every Project room", () => {
    VILLAGE_LEVEL.stations.forEach((station, stationIndex) => {
      const plan = planRandomPath(station.agentSlots[0], initialState(10_000 + stationIndex));
      expect(plan, station.id).not.toBeNull();
      expect(navigationPathIsWalkable(plan!.points), station.id).toBe(true);
      expect(routeDistance(plan!.points), station.id).toBeLessThanOrEqual(VILLAGE_LEVEL.navigation.destinationMaxPathDistance);
    });
  });

  test("keeps room walls solid while every declared entrance stays connected", () => {
    const boundaryIds = new Set(VILLAGE_LEVEL.boundaries.map((boundary) => boundary.id));
    const requiredPerimeterWalls = [
      "northwest-upper-wall", "northwest-left-wall", "northwest-lower-wall", "northwest-right-wall",
      "north-upper-wall", "north-left-wall", "north-right-wall", "north-lower-left-wall", "north-lower-right-wall",
      "northeast-upper-wall", "northeast-left-wall", "northeast-lower-wall", "northeast-right-wall",
      "southwest-upper-wall", "southwest-left-wall", "southwest-right-wall", "southwest-lower-wall",
      "south-upper-left-wall", "south-upper-right-wall", "south-left-wall", "south-right-wall", "south-lower-wall",
      "southeast-upper-wall", "southeast-left-wall", "southeast-right-wall", "southeast-lower-wall",
      "northwest-upper-left-corner-wall", "northeast-upper-right-corner-wall",
      "southwest-upper-left-corner-wall", "southeast-upper-right-corner-wall",
    ];
    expect(requiredPerimeterWalls.filter((wallId) => !boundaryIds.has(wallId))).toEqual([]);

    VILLAGE_LEVEL.boundaries.forEach((boundary) => {
      boundary.collisionPolygons.forEach((polygon) => {
        const sample = [polygon[0], polygon[1], polygon[polygon.length - 1]]
          .reduce((sum, point) => ({ x: sum.x + point.x / 3, y: sum.y + point.y / 3 }), { x: 0, y: 0 });
        expect(footPointIsBlocked(sample), boundary.id).toBe(true);
      });
    });

    const centralHub = { x: 650, y: 430 };
    VILLAGE_LEVEL.portals.forEach((portal) => {
      expect(pointIsWalkable(portal.inside), `${portal.stationId} inside`).toBe(true);
      expect(pointIsWalkable(portal.outside), `${portal.stationId} outside`).toBe(true);
      expect(navigationSegmentIsWalkable(portal.inside, portal.outside), `${portal.stationId} portal`).toBe(true);
      const station = VILLAGE_LEVEL.stations.find((candidate) => candidate.id === portal.stationId)!;
      expect(planPath(station.agentSlots[0], portal.inside), `${portal.stationId} interior`).not.toBeNull();
      expect(planPath(portal.outside, centralHub), `${portal.stationId} exterior`).not.toBeNull();
      const route = planPath(station.agentSlots[0], centralHub);
      expect(route, portal.stationId).not.toBeNull();
      expect(navigationPathIsWalkable(route!), portal.stationId).toBe(true);
    });

    const exits = stationExitDiagnostics();
    expect(exits.every((diagnostic) => diagnostic.transitionCount > 0), JSON.stringify(exits)).toBe(true);
    expect(exits.filter((diagnostic) => diagnostic.unauthorizedTransitionCount > 0), JSON.stringify(exits)).toEqual([]);
  });

  test("selects varied destinations instead of replaying a fixed loop", () => {
    let position = VILLAGE_LEVEL.stations[2].agentSlots[3];
    let state = initialState(0x5eed1234);
    const destinations = new Set<string>();
    for (let index = 0; index < 12; index += 1) {
      const plan = planRandomPath(position, state);
      expect(plan).not.toBeNull();
      expect(navigationPathIsWalkable(plan!.points)).toBe(true);
      destinations.add(plan!.destinationKey);
      position = destination(plan!);
      state = plan!;
    }
    expect(destinations.size).toBeGreaterThanOrEqual(10);
  });

  test("different Agents do not collapse onto one destination", () => {
    const start = VILLAGE_LEVEL.stations[3].agentSlots[0];
    const destinations = new Set(
      Array.from({ length: 12 }, (_, index) => planRandomPath(start, initialState(500 + index))?.destinationKey),
    );
    destinations.delete(undefined);
    expect(destinations.size).toBeGreaterThanOrEqual(8);
  });
});
