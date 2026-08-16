import { Controller, Get, Post, Patch, Param, Body } from '@nestjs/common';
import { KafkaService } from '../kafka/kafka.service';
import { EventsGateway } from '../websocket/events.gateway';

@Controller('api/v1')
export class TelemetryController {
  constructor(
    private readonly kafkaService: KafkaService,
    private readonly eventsGateway: EventsGateway,
  ) {}

  // ---------------------------------------------------------------------------
  // 1. SYSTEM HEALTH
  // ---------------------------------------------------------------------------
  @Get('health')
  getHealth() {
    return {
      status: 'OK',
      service: 'Smurf NestJS Track B Agriculture Backend',
      timestamp: Date.now(),
      webSocketClients: this.eventsGateway.getClientCount(),
    };
  }

  // ---------------------------------------------------------------------------
  // 2. TELEMETRY & WINDOWING APIs
  // ---------------------------------------------------------------------------
  @Get('telemetry/latest')
  getLatestTelemetry() {
    return this.kafkaService.getLatestTelemetry();
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
