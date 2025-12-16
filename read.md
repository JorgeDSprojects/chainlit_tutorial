chainlit run app.py
uvicorn main:app --reload
docker exec -it ollama-infra ollama list



NAME                                                        ID              SIZE      MODIFIED    
llama2:latest                                               78e26419b446    3.8 GB    5 days ago
qwen2.5:0.5b                                                a8b0c5157701    397 MB    6 days ago
hf.co/unsloth/Ministral-3-14B-Instruct-2512-GGUF:Q4_K_XL    0aebbc2bfe40    9.2 GB    7 days ago
llama3.2-vision:latest                                      6f2f9757ae97    7.8 GB    8 days ago
deepseek-r1:8b                                              6995872bfe4c    5.2 GB    13 days ago
deepseek-r1:1.5b                                            e0979632db5a    1.1 GB    13 days ago