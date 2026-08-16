import { NestFactory } from '@nestjs/core';
import { WsAdapter } from '@nestjs/platform-ws';
import { AppModule } from './app.module';
import * as dotenv from 'dotenv';

dotenv.config();

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  app.useWebSocketAdapter(new WsAdapter(app));

  const port = process.env.PORT || 8000;
  await app.listen(port);
  console.log(`🚀 [NestJS Backend] Server running on http://localhost:${port}`);
  console.log(`🔌 [NestJS WebSocket Gateway] Available at ws://localhost:${port}/ws`);
}

bootstrap();
