export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ValidationError extends ApiError {
  fields: Record<string, string>;

  constructor(fields: Record<string, string>) {
    super(422, "Validation error");
    this.name = "ValidationError";
    this.fields = fields;
  }
}
