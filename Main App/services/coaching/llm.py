from services.config.workout_config import PROMPT


class LLMCoach:
    def __init__(self, gemini_client):
        self.client = gemini_client
        self.history = []
        self.system_prompt = PROMPT

    def give_feedback(self, event, issue):
        prompt = f"Event: {event}"

        if issue:
            prompt += f" Form Issue: {issue}"

        conversation = "\n".join(
            f"{message['role'].title()}: {message['content']}"
            for message in self.history[-10:]
        )
        contents = f"{conversation}\nUser: {prompt}" if conversation else prompt

        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents,
            config={
                "system_instruction": self.system_prompt,
                "temperature": 0.4,
            },
        )

        text = (response.text or "").strip()
        self.history.append({"role": "assistant", "content": text})

        return text
    