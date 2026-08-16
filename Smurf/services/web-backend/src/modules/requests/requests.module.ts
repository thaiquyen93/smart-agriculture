import { Module } from '@nestjs/common';
import { RequestsController } from './requests.controller';
import { KafkaModule } from '../kafka/kafka.module';

@Module({
  imports: [KafkaModule],
  controllers: [RequestsController],
})
export class RequestsModule {}
