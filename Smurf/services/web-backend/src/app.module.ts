import { Module } from '@nestjs/common';
import { DbModule } from './modules/db/db.module';
import { KafkaModule } from './modules/kafka/kafka.module';
import { WebsocketModule } from './modules/websocket/websocket.module';
import { TelemetryModule } from './modules/telemetry/telemetry.module';
import { PlansModule } from './modules/plans/plans.module';
import { TasksModule } from './modules/tasks/tasks.module';
import { AgentlogModule } from './modules/agentlog/agentlog.module';
import { RequestsModule } from './modules/requests/requests.module';

import { AppController } from './app.controller';

@Module({
  imports: [
    DbModule,
    KafkaModule,
    WebsocketModule,
    TelemetryModule,
    PlansModule,
    TasksModule,
    AgentlogModule,
    RequestsModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
