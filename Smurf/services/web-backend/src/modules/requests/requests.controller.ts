import { Controller, Post, Body, BadRequestException } from '@nestjs/common';
import { KafkaService } from '../kafka/kafka.service';

@Controller('api/v1/requests')
export class RequestsController {
  constructor(private readonly kafkaService: KafkaService) {}

  @Post()
  async submitRequest(@Body() body: { prompt: string; session_id?: string }) {
    if (!body || !body.prompt || !body.prompt.trim()) {
      throw new BadRequestException('Field "prompt" is required and cannot be empty.');
    }

    const result = await this.kafkaService.publishRequest({
      prompt: body.prompt.trim(),
      session_id: body.session_id,
    });

    return {
      status: 'ACCEPTED',
      message: 'Operator request received and forwarded to AI Multi-Agent Coordinator.',
      ...result,
    };
  }
}
