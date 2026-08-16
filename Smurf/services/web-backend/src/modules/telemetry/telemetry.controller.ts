import { Controller, Get, Post, Patch, Param, Body } from '@nestjs/common';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';
import { DbService } from '../db/db.service';

@Controller('api/v1')
export class TelemetryController {
  constructor(
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
    private readonly dbService: DbService,
  ) {}

  // ---------------------------------------------------------------------------
  // 1. SYSTEM HEALTH
  // ---------------------------------------------------------------------------
  @Get('health')
  getHealth() {
    return {
      status: 'OK',
      service: 'Smurf Smart Agriculture Backend',
      timestamp: Date.now(),
      webSocketsClients: this.eventsGateway.getClientCount(),
      track: 'Track B: Smart Agriculture',
    };
  }

  // ---------------------------------------------------------------------------
  // 2. TELEMETRY & WINDOWING APIs
  // ---------------------------------------------------------------------------
  @Get('telemetry/latest')
  getLatestTelemetry() {
    const memoryMap = this.kafkaService.getLatestTelemetryMap();
    const dbStates = this.dbService.getLatestDeviceStates();

    const expectedDevices = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01'];
    const nowMs = Date.now();

    return expectedDevices.map((code) => {
      const live = memoryMap.get(code) || dbStates[code] || null;

      if (!live) {
        return {
          device_code: code,
          device_id: code,
          status: 'OFFLINE',
          is_stale: true,
          age_sec: 999999,
          payload: {},
        };
      }

      // Calculate freshness
      const eventTimeSec = live.event_time || live.timestamp || live.created_at || live.db_created_at || (nowMs / 1000);
      const eventTimeMs = eventTimeSec > 1e11 ? eventTimeSec : eventTimeSec * 1000;
      const ageSec = Math.max(0, Math.floor((nowMs - eventTimeMs) / 1000));
      const isStale = ageSec > 120; // Stale if > 2 minutes without updates

      return {
        device_code: code,
        device_id: code,
        name: live.name || code,
        age_sec: ageSec,
        is_stale: isStale,
        status: isStale ? 'STALE' : 'ONLINE',
        last_updated: new Date(eventTimeMs).toISOString(),
        metrics: {
          soil_moisture: live.soil_moisture,
          temperature: live.temperature,
          humidity: live.humidity,
          flow_rate: live.flow_rate,
          power: live.power,
          ph: live.ph,
          level: live.level,
          lux: live.lux,
          pump_status: live.status,
        },
        raw: live,
      };
    });
  }

  @Get('devices')
  getDevices() {
    return this.getLatestTelemetry();
  }

  @Get('telemetry/history/:deviceId')
  getDeviceHistory(@Param('deviceId') deviceId: string) {
    // Default to 25 records to match the frontend chart width
    return this.dbService.getDeviceHistory(deviceId, 25);
  }

  @Get('telemetry/windows')
  getSlidingWindows() {
    return this.kafkaService.getSlidingWindows();
  }

  @Get('telemetry/hourly')
  getHourlyWindows() {
    return this.kafkaService.getHourlyWindows();
  }

  // ---------------------------------------------------------------------------
  // 3. HUMAN-IN-THE-LOOP IRRIGATION APPROVAL APIs
  // ---------------------------------------------------------------------------
  @Get('irrigation/plans')
  getIrrigationPlans() {
    return this.kafkaService.getIrrigationPlans();
  }

  @Post('irrigation/plans/:planId/approve')
  approvePlan(@Param('planId') planId: string, @Body() body?: { manager_note?: string }) {
    return this.kafkaService.approvePlan(planId, body?.manager_note);
  }

  @Post('irrigation/plans/:planId/reject')
  rejectPlan(@Param('planId') planId: string, @Body() body?: { reason?: string }) {
    return this.kafkaService.rejectPlan(planId, body?.reason);
  }

  // ---------------------------------------------------------------------------
  // 4. ALERTS & ANOMALIES APIs
  // ---------------------------------------------------------------------------
  @Get('alerts')
  getAlerts() {
    return this.kafkaService.getAlerts();
  }

  @Patch('alerts/:alertId/ack')
  ackAlert(@Param('alertId') alertId: string) {
    return this.kafkaService.ackAlert(alertId);
  }

  // ---------------------------------------------------------------------------
  // 5. FIELD INSPECTION TASKS APIs
  // ---------------------------------------------------------------------------
  @Get('tasks')
  getTasks() {
    return this.kafkaService.getInspectionTasks();
  }

  @Post('tasks')
  createTask(@Body() body: any) {
    return this.kafkaService.createInspectionTask(body);
  }

  @Patch('tasks/:taskId/verify')
  verifyTask(@Param('taskId') taskId: string, @Body() body?: { note?: string }) {
    return this.kafkaService.verifyTask(taskId, body?.note);
  }

  // ---------------------------------------------------------------------------
  // 6. MULTI-AGENT REASONING TRACES & AI COPILOT QUERY APIs
  // ---------------------------------------------------------------------------
  @Get('agents/logs')
  getAgentLogs() {
    return this.kafkaService.getAgentLogs();
  }

  @Post('ai/query')
  handleAIQuery(@Body() body: { prompt: string }) {
    return this.kafkaService.handleAIQuery(body?.prompt || 'Thời tiết và độ ẩm đất hiện tại ra sao?');
  }
}
