#!/usr/bin/env python3
"""Test script for Ollama LLM adapter."""

from lecture_auto.llm_config import LLMConfig
from lecture_auto.llm_adapter import OllamaLLMAdapter

# Sample transcript text to refine
raw_transcript = """
안녕하세요  오늘은   머신러닝의   기본 개념에  대해   알아보겠습니다
먼저   슈퍼바이즈드  러닝에  대해  설명하겠습니다   이것은    레이블이   있는   데이터를
사용해서  모델을   학습시키는   방법이구요    그  다음에  언슈퍼바이즈드  러닝도  있습니다
"""

# Sample note generation template
note_template = """
# 강의 노트

## 주요 개념
[여기에 주요 개념 정리]

## 상세 내용
[여기에 상세 내용 정리]

## 요약
[여기에 핵심 요약]
"""

def test_ollama_refine():
    """Test transcript refinement with Ollama."""
    print("=" * 60)
    print("TEST 1: Transcript Refinement (Korean)")
    print("=" * 60)
    
    config = LLMConfig(
        provider="ollama",
        model_name="gemma4:31b-cloud",
        language="Korean",
        chunk_size=4000,
    )
    
    adapter = OllamaLLMAdapter(config)
    
    print("\n[Original Transcript]")
    print(raw_transcript)
    
    print("\n[Refining transcript...]")
    refined = adapter.refine_transcript(
        raw_transcript,
        context_topic="머신러닝 기초"
    )
    
    print("\n[Refined Transcript]")
    print(refined)
    print("\n" + "=" * 60 + "\n")


def test_ollama_notes():
    """Test note generation with Ollama."""
    print("=" * 60)
    print("TEST 2: Note Generation (Korean)")
    print("=" * 60)
    
    config = LLMConfig(
        provider="ollama",
        model_name="gemma4:31b-cloud",
        language="Korean",
        chunk_size=4000,
    )
    
    adapter = OllamaLLMAdapter(config)
    
    # Use refined text for notes
    transcript_for_notes = """
안녕하세요. 오늘은 머신러닝의 기본 개념에 대해 알아보겠습니다.
먼저 슈퍼바이즈드 러닝에 대해 설명하겠습니다. 이것은 레이블이 있는 데이터를
사용해서 모델을 학습시키는 방법입니다. 그 다음에 언슈퍼바이즈드 러닝도 있습니다.
"""
    
    print("\n[Template]")
    print(note_template)
    
    print("\n[Generating notes...]")
    notes = adapter.generate_notes(
        transcript_for_notes,
        note_template,
        context_topic="머신러닝 기초"
    )
    
    print("\n[Generated Notes]")
    print(notes)
    print("\n" + "=" * 60 + "\n")


def test_english_refine():
    """Test with English text."""
    print("=" * 60)
    print("TEST 3: Transcript Refinement (English)")
    print("=" * 60)
    
    english_text = """
hello   everyone    today  we will  learn  about    the  basics  of   machine  learning
first   let me  explain  supervised   learning  which   uses   labeled   data  to  train  models
then we  will  also  cover  unsupervised  learning
"""
    
    config = LLMConfig(
        provider="ollama",
        model_name="gemma4:31b-cloud",
        language="English",
        chunk_size=4000,
    )
    
    adapter = OllamaLLMAdapter(config)
    
    print("\n[Original Transcript]")
    print(english_text)
    
    print("\n[Refining transcript...]")
    refined = adapter.refine_transcript(
        english_text,
        context_topic="Machine Learning Basics"
    )
    
    print("\n[Refined Transcript]")
    print(refined)
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    print("\n🚀 Testing Ollama LLM Adapter\n")
    
    try:
        # Test 1: Korean transcript refinement
        test_ollama_refine()
        
        # Test 2: Korean note generation
        test_ollama_notes()
        
        # Test 3: English transcript refinement
        test_english_refine()
        
        print("✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
