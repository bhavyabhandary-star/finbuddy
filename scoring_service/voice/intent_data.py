"""Synthetic Hindi/Tamil/English intent training examples for F-007/9.

HONEST NOTE ON WHY THIS MODEL CHOICE: an earlier test with
paraphrase-multilingual-MiniLM-L12-v2 (the smaller, more common choice)
scored well on Hindi but got 2/3 Tamil test queries WRONG with near-noise
similarity scores. Switched to sentence-transformers/LaBSE (109 languages,
Google) after verifying empirically it gets 8/8 correct on held-out Hindi
+ Tamil test queries with strong confidence margins (0.65-0.93 similarity).
Don't swap the embedding model without re-running that check -- multilingual
coverage varies a lot model to model and claims about "supports language X"
are not reliable without testing the actual language pair.

These are synthetic/authored examples, not sourced from real user
conversations (no real WhatsApp data exists for this project) -- same
honesty caveat as the rest of the synthetic data in this repo.
"""

from __future__ import annotations

INTENT_EXAMPLES: dict[str, list[str]] = {
    "loan_status": [
        # Hindi
        "मेरे लोन का स्टेटस क्या है",
        "मेरा लोन अभी तक अप्रूव क्यों नहीं हुआ",
        "मेरी एप्लीकेशन का क्या हुआ",
        "क्या मेरा लोन पास हो गया है",
        "मुझे अपने लोन की स्थिति जाननी है",
        "लोन कब तक मिलेगा",
        # Tamil
        "என் கடன் நிலை என்ன",
        "என் கடன் விண்ணப்பம் இன்னும் ஏன் அங்கீகரிக்கப்படவில்லை",
        "எனது விண்ணப்பத்திற்கு என்ன ஆனது",
        "என் கடன் அங்கீகரிக்கப்பட்டதா",
        "எனக்கு எப்போது கடன் கிடைக்கும்",
        "என் கடன் விண்ணப்ப நிலையை தெரிந்து கொள்ள வேண்டும்",
        # English
        "What is the status of my loan application",
        "Has my loan been approved yet",
        "When will I get my loan",
        "I want to check my application status",
    ],
    "why_data_needed": [
        "आप मेरा UPI डेटा क्यों चाहते हैं",
        "मेरा बैंक डेटा लेने का कारण क्या है",
        "मेरी ट्रांजैक्शन हिस्ट्री क्यों मांगी जा रही है",
        "यह ऐप मेरा फाइनेंशियल डेटा क्यों इस्तेमाल करता है",
        "मेरी जानकारी सुरक्षित है क्या",
        "डेटा शेयर करना क्यों जरूरी है",
        "நீங்கள் ஏன் என் UPI தரவு தேவை",
        "என் வங்கி தரவை ஏன் கேட்கிறீர்கள்",
        "எனது பரிவர்த்தனை வரலாறு ஏன் தேவை",
        "இந்த ஆப் ஏன் என் நிதி தரவை பயன்படுத்துகிறது",
        "என் தகவல் பாதுகாப்பானதா",
        "தரவு பகிர்வது ஏன் அவசியம்",
        "Why do you need my UPI transaction data",
        "Why is my bank data required for this",
        "Is my financial information safe with you",
        "Why do you need my transaction history",
    ],
    "limit_reduced": [
        "मेरी लिमिट क्यों घटाई गई",
        "मेरा क्रेडिट लिमिट कम क्यों हो गया",
        "पहले ज्यादा लिमिट थी अब कम क्यों है",
        "मेरी अप्रूव्ड राशि कम क्यों कर दी",
        "लिमिट कम होने का कारण बताएं",
        "मेरा लोन अमाउंट घटा दिया गया, क्यों",
        "என் கடன் வரம்பு ஏன் குறைக்கப்பட்டது",
        "எனது கிரெடிட் லிமிட் ஏன் குறைந்தது",
        "முன்பு அதிக வரம்பு இருந்தது இப்போது ஏன் குறைவு",
        "எனது அங்கீகரிக்கப்பட்ட தொகை ஏன் குறைக்கப்பட்டது",
        "வரம்பு குறைந்ததற்கான காரணத்தை சொல்லுங்கள்",
        "என் கடன் தொகை ஏன் குறைந்தது",
        "Why was my credit limit reduced",
        "My approved amount is lower than before, why",
        "Why did my limit go down",
        "Can you explain why my limit was cut",
    ],
    "repayment_help": [
        "मुझे लोन चुकाने में मदद चाहिए",
        "मैं समय पर पेमेंट नहीं कर पाया, अब क्या करूं",
        "रीपेमेंट का शेड्यूल क्या है",
        "क्या मैं किस्त की तारीख बदल सकता हूं",
        "मेरा पेमेंट मिस हो गया, मदद करें",
        "लोन चुकाने का तरीका बताएं",
        "எனக்கு கடன் திருப்பிச் செலுத்த உதவி வேண்டும்",
        "நான் சரியான நேரத்தில் பணம் செலுத்த முடியவில்லை, இப்போது என்ன செய்வது",
        "திருப்பிச் செலுத்தும் அட்டவணை என்ன",
        "தவணை தேதியை மாற்ற முடியுமா",
        "என் கட்டணம் தவறவிட்டேன், உதவி செய்யுங்கள்",
        "கடனை திருப்பிச் செலுத்தும் முறையை சொல்லுங்கள்",
        "I need help repaying my loan",
        "I missed a payment, what should I do",
        "Can I change my repayment date",
        "What is my repayment schedule",
    ],
    "general_query": [
        "यह ऐप कैसे काम करता है",
        "फिनबडी क्या है",
        "मुझे और लोन प्रोडक्ट के बारे में बताएं",
        "कस्टमर सपोर्ट से कैसे बात करूं",
        "नमस्ते",
        "धन्यवाद",
        "இந்த ஆப் எப்படி வேலை செய்கிறது",
        "ஃபின்பட்டி என்றால் என்ன",
        "மேலும் கடன் தயாரிப்புகளைப் பற்றி சொல்லுங்கள்",
        "வாடிக்கையாளர் ஆதரவுடன் எப்படி பேசுவது",
        "வணக்கம்",
        "நன்றி",
        "How does this app work",
        "What is FinBuddy",
        "Hello",
        "Thank you",
    ],
}


def flatten() -> tuple[list[str], list[str]]:
    """Returns (texts, labels), same order guaranteed."""
    texts, labels = [], []
    for intent, examples in INTENT_EXAMPLES.items():
        texts.extend(examples)
        labels.extend([intent] * len(examples))
    return texts, labels
