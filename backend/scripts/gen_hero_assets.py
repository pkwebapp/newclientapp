"""One-time script: generate hero face photos (Nano Banana) and upload to Cloudinary."""
import asyncio
import base64
import os

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent  # noqa: E402

OUT = "/app/backend/scripts/hero_out"
os.makedirs(OUT, exist_ok=True)

API_KEY = os.getenv("EMERGENT_LLM_KEY")
MODEL = "gemini-3.1-flash-image-preview"

SELFIE_PROMPT = (
    "Photorealistic vertical smartphone selfie of a young Indian woman in her mid-20s with wavy dark hair, "
    "warm genuine smile, looking straight into the front camera, arm slightly extended selfie angle. "
    "Soft natural window light, warm neutral beige-taupe background, minimal and clean. "
    "Shot on a phone front camera, shallow depth of field, warm color grade, editorial quality. Portrait 3:4."
)

EVENT_PROMPTS = [
    (
        "event1",
        "Using the woman in this reference photo, create a photorealistic candid wedding reception photo of her "
        "laughing with two friends, holding a drink, warm string lights bokeh in the background, "
        "professional event photography, warm color grade, square crop.",
    ),
    (
        "event2",
        "Using the woman in this reference photo, create a photorealistic candid photo of her dancing joyfully "
        "at an elegant sangeet celebration, motion and happiness, warm ambient lighting, guests softly blurred behind, "
        "professional event photography, warm color grade, square crop.",
    ),
    (
        "event3",
        "Using the woman in this reference photo, create a photorealistic candid group photo of her posing with "
        "three well-dressed friends at a wedding, everyone smiling at the camera, warm golden-hour light, "
        "professional event photography, warm color grade, square crop.",
    ),
]


async def gen(prompt: str, name: str, reference_b64: str | None = None) -> str:
    chat = LlmChat(api_key=API_KEY, session_id=f"hero-{name}", system_message="You are an expert photographer AI.")
    chat.with_model("gemini", MODEL).with_params(modalities=["image", "text"])
    if reference_b64:
        msg = UserMessage(text=prompt, file_contents=[ImageContent(reference_b64)])
    else:
        msg = UserMessage(text=prompt)
    _, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise RuntimeError(f"No image returned for {name}")
    path = os.path.join(OUT, f"{name}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(images[0]["data"]))
    print(f"saved {path} ({os.path.getsize(path) // 1024} KB)")
    return path


async def main():
    selfie_path = await gen(SELFIE_PROMPT, "selfie")
    with open(selfie_path, "rb") as f:
        ref_b64 = base64.b64encode(f.read()).decode("utf-8")
    for name, prompt in EVENT_PROMPTS:
        try:
            await gen(prompt, name, ref_b64)
        except Exception as e:
            print(f"FAILED {name}: {e}")

    # Upload to Cloudinary
    import cloudinary
    import cloudinary.uploader

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    for fn in sorted(os.listdir(OUT)):
        if not fn.endswith(".png"):
            continue
        res = cloudinary.uploader.upload(
            os.path.join(OUT, fn),
            public_id=f"pikconnect/hero/{fn[:-4]}",
            overwrite=True,
            resource_type="image",
        )
        print(f"UPLOADED {fn}: {res['secure_url']}")


if __name__ == "__main__":
    asyncio.run(main())
