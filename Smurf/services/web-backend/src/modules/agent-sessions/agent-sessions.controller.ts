import { Controller, Post, Get, Param, Body, Res, Logger, HttpException, HttpStatus } from '@nestjs/common';
import { Response } from 'express';
import { KafkaService } from '../kafka/kafka.service';

/**
 * Proxy controller for agent-core Multi-Agent sessions API.
 *
 * Forwards requests from the frontend (port 3000) through web-backend (port 8000)
 * to agent-core (port 8100), avoiding CORS issues and keeping the frontend
 * agnostic of internal service topology.
 *
 * Endpoints:
 *   POST /api/v1/agent/sessions           -> Create new agent session
 *   GET  /api/v1/agent/sessions           -> List all sessions
 *   GET  /api/v1/agent/sessions/:id       -> Get session state
 *   GET  /api/v1/agent/sessions/:id/stream -> SSE live trace (proxy)
 *   POST /api/v1/agent/approvals/:id      -> Approve/reject pending plans
 *   GET  /api/v1/agent/events             -> Get recent agent events from Kafka
 */
@Controller('api/v1/agent')
export class AgentSessionsController {
  private readonly logger = new Logger(AgentSessionsController.name);
  private readonly agentCoreUrl: string;

  constructor(private readonly kafkaService: KafkaService) {
    this.agentCoreUrl = process.env.AGENT_CORE_URL || 'http://localhost:8100';
    this.logger.log(`Agent-core URL: ${this.agentCoreUrl}`);
  }

  /**
   * POST /api/v1/agent/sessions
   * Create a new Multi-Agent session. Proxies to agent-core.
   */
  @Post('sessions')
  async createSession(@Body() body: { user_request: string; user_id?: string; metadata?: any }) {
    if (!body?.user_request?.trim()) {
      throw new HttpException('Field "user_request" is required.', HttpStatus.BAD_REQUEST);
    }

    try {
      const response = await fetch(`${this.agentCoreUrl}/api/v1/agent/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.logger.error(`agent-core returned ${response.status}: ${errorText}`);
        throw new HttpException(
          `Agent-core error: ${errorText}`,
          response.status,
        );
      }

      const data = await response.json();
      this.logger.log(`Created agent session: ${data.session_id}`);
      return data;
    } catch (err: any) {
      if (err instanceof HttpException) throw err;
      this.logger.error(`Failed to reach agent-core: ${err?.message}`);
      throw new HttpException(
        'Agent-core service unavailable. Multi-Agent AI is offline.',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  /**
   * GET /api/v1/agent/sessions
   * List all agent sessions (proxy to agent-core).
   */
  @Get('sessions')
  async listSessions() {
    try {
      const response = await fetch(`${this.agentCoreUrl}/api/v1/sessions`);
      if (!response.ok) {
        return { sessions: [], total: 0, agent_core_status: 'error' };
      }
      return await response.json();
    } catch {
      return { sessions: [], total: 0, agent_core_status: 'offline' };
    }
  }

  /**
   * GET /api/v1/agent/sessions/:id
   * Get session state snapshot (proxy to agent-core).
   */
  @Get('sessions/:id')
  async getSession(@Param('id') sessionId: string) {
    try {
      const response = await fetch(`${this.agentCoreUrl}/api/v1/sessions/${sessionId}`);
      if (!response.ok) {
        throw new HttpException('Session not found', response.status);
      }
      return await response.json();
    } catch (err: any) {
      if (err instanceof HttpException) throw err;
      throw new HttpException('Agent-core service unavailable', HttpStatus.SERVICE_UNAVAILABLE);
    }
  }

  /**
   * GET /api/v1/agent/sessions/:id/stream
   * Proxy SSE (Server-Sent Events) stream from agent-core.
   * This allows the frontend to receive real-time agent event updates.
   */
  @Get('sessions/:id/stream')
  async streamSession(@Param('id') sessionId: string, @Res() res: Response) {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.flushHeaders();

    try {
      const upstream = await fetch(`${this.agentCoreUrl}/api/v1/sessions/${sessionId}/stream`);

      if (!upstream.ok || !upstream.body) {
        res.write('event: error\ndata: {"message": "Failed to connect to agent-core stream"}\n\n');
        res.end();
        return;
      }

      // Pipe the SSE stream from agent-core to the frontend client
      const reader = upstream.body.getReader();
      const decoder = new TextDecoder();

      const pump = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            res.write(chunk);
          }
        } catch (e: any) {
          this.logger.warn(`SSE stream interrupted: ${e?.message}`);
        } finally {
          res.end();
        }
      };

      // Handle client disconnect
      res.on('close', () => {
        reader.cancel().catch(() => {});
      });

      await pump();
    } catch (err: any) {
      this.logger.error(`Failed to proxy SSE stream: ${err?.message}`);
      res.write('event: error\ndata: {"message": "Agent-core unavailable"}\n\n');
      res.end();
    }
  }

  /**
   * POST /api/v1/agent/approvals/:id
   * Approve or reject a pending action plan (proxy to agent-core).
   */
  @Post('approvals/:id')
  async approveSession(
    @Param('id') sessionId: string,
    @Body() body: { approved: boolean; reason?: string },
  ) {
    try {
      const response = await fetch(`${this.agentCoreUrl}/api/v1/approvals/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new HttpException(errorText, response.status);
      }

      return await response.json();
    } catch (err: any) {
      if (err instanceof HttpException) throw err;
      throw new HttpException('Agent-core service unavailable', HttpStatus.SERVICE_UNAVAILABLE);
    }
  }

  /**
   * GET /api/v1/agent/events
   * Get recent agent events received via Kafka (from local cache).
   */
  @Get('events')
  getAgentEvents() {
    return {
      total: this.kafkaService.getAgentEvents().length,
      data: this.kafkaService.getAgentEvents().slice(0, 50),
    };
  }
}
