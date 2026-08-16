import { Controller, Get, Query } from '@nestjs/common';
import { DbService } from '../db/db.service';

@Controller('api/v1/agent-logs')
export class AgentlogController {
  constructor(private readonly dbService: DbService) {}

  @Get()
  getAgentLogs(
    @Query('session_id') sessionId?: string,
    @Query('agent') agentName?: string,
    @Query('limit') limit: number = 50,
  ) {
    const logs = this.dbService.getAgentLogs(sessionId, agentName, Number(limit) || 50);
    return {
      total: logs.length,
      session_id_filter: sessionId || 'ALL',
      agent_filter: agentName || 'ALL',
      data: logs,
    };
  }
}
