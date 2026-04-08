#!/usr/bin/env python3
"""Test Ollama transcript refinement with actual CLI integration."""

import sys
from pathlib import Path

# Test with the actual service
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService
from lecture_auto.llm_config import LLMConfig
from lecture_auto.llm_adapter import OllamaLLMAdapter

def test_cli_integration():
    """Test transcript refinement through service layer."""
    
    # Setup
    workspace = Path.home() / "lecture_notes"
    metadata_file = workspace / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)
    
    # Create Ollama adapter
    llm_config = LLMConfig(
        provider="ollama",
        model_name="gemma4:31b-cloud",
        language="Korean",
        chunk_size=4000,
    )
    llm_adapter = OllamaLLMAdapter(llm_config)
    
    # Create service with Ollama adapter
    service = SessionService(
        store=store,
        runtime_adapter=None,
        stt_config=None,
        local_stt_adapter=None,
        api_stt_adapter=None,
        llm_adapter=llm_adapter,
        audio_format="mp3",
    )
    
    # Read test transcript
    test_transcript_path = workspace / "test_session" / "transcript.txt"
    if not test_transcript_path.exists():
        print(f"❌ Test transcript not found at {test_transcript_path}")
        return False
    
    with open(test_transcript_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    print("=" * 60)
    print("Testing Ollama Transcript Refinement via Service Layer")
    print("=" * 60)
    
    print("\n[Original Transcript]")
    print(raw_text)
    print()
    
    print("[Refining with Ollama (gemma4:31b-cloud)...]")
    try:
        refined_text = llm_adapter.refine_transcript(
            raw_text, 
            context_topic="딥러닝 기초"
        )
        
        print("\n[Refined Transcript]")
        print(refined_text)
        print()
        
        # Save refined version
        refined_path = workspace / "test_session" / "transcript_refined.txt"
        with open(refined_path, 'w', encoding='utf-8') as f:
            f.write(refined_text)
        
        print(f"✅ Refined transcript saved to: {refined_path}")
        print()
        
        # Compare lengths
        print(f"Original length: {len(raw_text)} chars")
        print(f"Refined length: {len(refined_text)} chars")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during refinement: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_note_generation():
    """Test note generation with Ollama."""
    
    workspace = Path.home() / "lecture_notes"
    
    # Create Ollama adapter
    llm_config = LLMConfig(
        provider="ollama",
        model_name="gemma4:31b-cloud",
        language="Korean",
        chunk_size=4000,
    )
    llm_adapter = OllamaLLMAdapter(llm_config)
    
    # Read refined transcript
    refined_path = workspace / "test_session" / "transcript_refined.txt"
    if not refined_path.exists():
        print(f"❌ Refined transcript not found at {refined_path}")
        return False
    
    with open(refined_path, 'r', encoding='utf-8') as f:
        transcript = f.read()
    
    # Simple template
    template = """
# 강의 요약

## 주요 주제
[여기에 주요 주제를 작성]

## 핵심 개념
[여기에 핵심 개념을 나열]

## 상세 내용
[여기에 상세 내용을 정리]

## 중요 용어
[여기에 중요 용어를 정리]
"""
    
    print("=" * 60)
    print("Testing Ollama Note Generation")
    print("=" * 60)
    
    print("\n[Generating notes with Ollama...]")
    try:
        notes = llm_adapter.generate_notes(
            transcript,
            template,
            context_topic="딥러닝 기초"
        )
        
        print("\n[Generated Notes]")
        print(notes)
        print()
        
        # Save notes
        notes_path = workspace / "test_session" / "notes.md"
        with open(notes_path, 'w', encoding='utf-8') as f:
            f.write(notes)
        
        print(f"✅ Notes saved to: {notes_path}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during note generation: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🚀 Testing Ollama Integration with CLI Service Layer\n")
    
    success = True
    
    # Test 1: Transcript refinement
    if not test_cli_integration():
        success = False
    
    # Test 2: Note generation
    if not test_note_generation():
        success = False
    
    if success:
        print("\n✅ All integration tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
