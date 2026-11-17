"""Gọi Claude để trích xuất có cấu trúc. Có lớp giả (FakeLLM) để kiểm thử không cần API."""
from __future__ import annotations

import os


class LLMError(RuntimeError):
    pass


class ClaudeLLM:
    def __init__(self, model: str = "claude-sonnet-5-5", max_tokens: int = 16000,
                 api_key: str | None = None):
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("Chưa có ANTHROPIC_API_KEY (đặt biến môi trường hoặc file .env).")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def structured(self, system: str, content: list[dict], schema: dict,
                   tool_name: str = "ghi_ket_qua") -> dict:
        """Lấy kết quả JSON đúng schema qua tool_use.

        Một số mô hình không cho ép tool_choice (type tool/any) nên dùng chế độ tự động,
        yêu cầu rõ trong lời nhắc và thử lại nếu mô hình chưa gọi công cụ."""
        tool = {"name": tool_name, "description": "Ghi kết quả phân tích có cấu trúc.",
                "input_schema": schema}
        sys_txt = system + f"\n\nKhi xong, BẮT BUỘC gọi công cụ `{tool_name}` để ghi kết quả; không trả lời bằng văn bản thường."
        messages = [{"role": "user", "content": content}]
        for _ in range(3):
            with self.client.messages.stream(
                model=self.model, max_tokens=self.max_tokens, system=sys_txt,
                tools=[tool], messages=messages,
            ) as stream:
                msg = stream.get_final_message()
            for b in msg.content:
                if b.type == "tool_use" and b.name == tool_name:
                    return dict(b.input)
            if msg.stop_reason == "max_tokens":
                raise LLMError("Kết quả quá dài, bị cắt giữa chừng (tăng llm.max_tokens trong config.yaml).")
            messages = [*messages,
                        {"role": "assistant", "content": [x.model_dump(exclude_none=True) for x in msg.content]},
                        {"role": "user", "content": f"Hãy gọi công cụ `{tool_name}` để ghi kết quả."}]
        raise LLMError("Mô hình không trả về kết quả có cấu trúc.")


class FakeLLM:
    """Dùng trong kiểm thử: trả lần lượt các kết quả dựng sẵn (hoặc gọi hàm)."""

    def __init__(self, responses):
        self.responses = responses
        self.calls: list[dict] = []

    def structured(self, system, content, schema, tool_name="ghi_ket_qua"):
        self.calls.append({"system": system, "content": content, "tool": tool_name})
        r = self.responses
        if callable(r):
            return r(system, content, schema)
        return r.pop(0) if isinstance(r, list) else r
