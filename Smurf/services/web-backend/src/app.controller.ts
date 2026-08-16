import { Controller, Get } from '@nestjs/common';

@Controller()
export class AppController {
  @Get()
  getRoot() {
    return {
      service: '🌱 Smurf Smart Agriculture Modular Backend',
      version: '1.0.0',
      track: 'Track B: Smart Agriculture',
      status: 'ONLINE',
      websocket_gateway: 'ws://localhost:8000/ws',
      endpoints: {
        health: '/api/v1/health',
        devices: '/api/v1/devices',
        telemetry_latest: '/api/v1/telemetry/latest',
        irrigation_plans: '/api/v1/plans',
        inspection_tasks: '/api/v1/tasks',
        agent_reasoning_logs: '/api/v1/agent-logs',
        operator_request: 'POST /api/v1/requests',
        approve_plan: 'PATCH /api/v1/plans/:id/approve',
        reject_plan: 'PATCH /api/v1/plans/:id/reject',
        verify_task: 'PATCH /api/v1/tasks/:id/verify',
      },
    };
  }
}
