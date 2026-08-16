import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
} from '@nestjs/websockets';
import { Server, WebSocket } from 'ws';

@WebSocketGateway({ path: '/ws' })
export class EventsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private activeClients: Set<WebSocket> = new Set();

  handleConnection(client: WebSocket) {
    this.activeClients.add(client);
    console.log(`[NestJS WebSocket] Client connected. Total: ${this.activeClients.size}`);
  }

  handleDisconnect(client: WebSocket) {
    this.activeClients.delete(client);
    console.log(`[NestJS WebSocket] Client disconnected. Total: ${this.activeClients.size}`);
  }

  broadcast(type: string, data: any) {
    const payload = JSON.stringify({ type, data, timestamp: Date.now() });
    this.activeClients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    });
  }

  getClientCount(): number {
    return this.activeClients.size;
  }
}
