from src.pipeline.compression.bm25_compressor import BM25Compressor


def test_compress_empty():
    compressor = BM25Compressor()
    assert compressor.compress("query", []) == []


def test_compress_short_chunk():
    compressor = BM25Compressor(sentences_per_chunk=5)
    chunks = [{"text_content": "Short sentence.", "id": "1"}]
    result = compressor.compress("query", chunks)
    assert len(result) == 1
    assert result[0]["text_content"] == "Short sentence."


def test_compress_long_chunk():
    compressor = BM25Compressor(sentences_per_chunk=2)
    long_text = "Machine learning is powerful. Deep learning uses neural networks. Natural language processing handles text. Computer vision processes images. Reinforcement learning optimizes decisions."
    chunks = [{"text_content": long_text, "id": "1"}]
    result = compressor.compress("neural networks deep learning", chunks)
    assert len(result) == 1
    assert result[0].get("compressed") is True
    assert result[0]["kept_sentences"] == 2


def test_compress_preserves_metadata():
    compressor = BM25Compressor(sentences_per_chunk=2)
    long_text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    chunks = [{"text_content": long_text, "id": "1", "metadata": {"doc_id": "test"}}]
    result = compressor.compress("first", chunks)
    assert result[0]["metadata"]["doc_id"] == "test"
