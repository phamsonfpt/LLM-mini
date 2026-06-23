import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Send, Bot, User, FileText, ChevronRight, Paperclip, Loader, Headphones, RefreshCw, BookOpen, Brain, Layers, X, Check, XCircle, Trash2, Link as LinkIcon, Plus, ArrowLeft } from 'lucide-react';

function Studio() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeNotebook, setActiveNotebook] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [studyGuide, setStudyGuide] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [podcastGenerating, setPodcastGenerating] = useState(false);
  const [audioUrl, setAudioUrl] = useState(null);
  
  // Quiz & Flashcard state
  const [showQuiz, setShowQuiz] = useState(false);
  const [showFlashcards, setShowFlashcards] = useState(false);
  const [podcastUrl, setPodcastUrl] = useState(null);
  const [currentFlashcard, setCurrentFlashcard] = useState(0);
  const [flashcardFlipped, setFlashcardFlipped] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState(null);

  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInputValue, setUrlInputValue] = useState('');
  const [uploadingDocs, setUploadingDocs] = useState([]);
  const [selectedCitation, setSelectedCitation] = useState(null);

  const messagesEndRef = useRef(null);

  // Auto scroll
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch data khi mount
  useEffect(() => {
    if (!id) return;
    
    const fetchData = async () => {
      try {
        const nbRes = await fetch('/api/notebooks');
        const nbs = await nbRes.json();
        const nb = nbs.find(n => n.id === id);
        if (nb) {
          setActiveNotebook(nb);
          
          const msgRes = await fetch(`/api/notebooks/${nb.id}/messages`);
          const msgs = await msgRes.json();
          if (msgs && msgs.length > 0) {
            setMessages(msgs);
          } else {
            setMessages([{ role: 'assistant', content: `Xin chào! Bạn đang ở sổ tay "${nb.title}". Hãy tải tài liệu hoặc gửi link cho tôi nhé!`, citations: [] }]);
          }

          const guideRes = await fetch(`/api/notebooks/${nb.id}/study-guide`);
          if (guideRes.ok) {
            const guide = await guideRes.json();
            setStudyGuide(guide);
          }

          const docRes = await fetch(`/api/notebooks/${nb.id}/documents`);
          if (docRes.ok) {
            const docs = await docRes.json();
            setDocuments(docs);
          }
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchData();
  }, [id]);

  useEffect(() => {
    // Note: The logic inside fetchData was called in the previous mount effect.
    // If you need specific re-fetching logic triggered by activeNotebook change,
    // implement it here.
  }, [activeNotebook]);

  // Polling Study Guide if it is null AND there are documents
  useEffect(() => {
    let intervalId;
    if (activeNotebook && !studyGuide && documents.length > 0) {
      intervalId = setInterval(async () => {
        try {
          const guideRes = await fetch(`/api/notebooks/${activeNotebook.id}/study-guide`);
          if (guideRes.ok) {
            const guide = await guideRes.json();
            if (guide) {
              setStudyGuide(guide);
              clearInterval(intervalId);
            }
          }
        } catch (e) {
          console.error("Lỗi khi poll Study Guide:", e);
        }
      }, 3000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeNotebook, studyGuide, documents]);

  const generatePodcast = async () => {
    setPodcastGenerating(true);
    try {
      await fetch('/api/podcast/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notebook_id: activeNotebook?.id || 'default' })
      });
      setTimeout(() => {
        setAudioUrl(`/api/podcast/audio/${activeNotebook?.id || 'default'}?t=${Date.now()}`);
        setPodcastGenerating(false);
      }, 2000);
    } catch (e) {
      console.error(e);
      setPodcastGenerating(false);
    }
  };

  const deleteNotebook = async () => {
    if (!activeNotebook) return;
    if (!window.confirm("Bạn có chắc chắn muốn xóa sổ tay này và toàn bộ dữ liệu bên trong không?")) return;
    try {
      const res = await fetch(`/api/notebooks/${activeNotebook.id}`, { method: 'DELETE' });
      if (res.ok) {
        navigate('/dashboard');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleUrlSubmit = async () => {
    if (!urlInputValue.trim() || !activeNotebook) return;
    
    // Basic URL validation
    let urlToSubmit = urlInputValue.trim();
    if (!urlToSubmit.startsWith('http://') && !urlToSubmit.startsWith('https://')) {
      urlToSubmit = 'https://' + urlToSubmit;
    }

    setLoading(true);
    setShowUrlInput(false);
    setUploadingDocs(prev => [...prev, { filename: urlToSubmit }]);
    
    try {
      const formData = new FormData();
      formData.append('url', urlToSubmit);
      formData.append('notebook_id', activeNotebook.id);

      const res = await fetch('/api/ingest/url', {
        method: 'POST',
        body: formData
      });
      
      if (!res.ok) {
        throw new Error(`Mã lỗi từ máy chủ: ${res.status}`);
      }

      await res.json();
      setUrlInputValue('');
      
      // Cập nhật lại danh sách documents
      const docRes = await fetch(`/api/notebooks/${activeNotebook.id}/documents`);
      if (docRes.ok) {
        setDocuments(await docRes.json());
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Lỗi khi nạp link: ${e.message}`, citations: [] }]);
    } finally {
      setLoading(false);
      setUploadingDocs(prev => prev.filter(d => d.filename !== urlToSubmit));
    }
  };

  const handleFileUpload = async (e) => {
    if (!activeNotebook) return;
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadingDocs(prev => [...prev, { filename: file.name }]);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('notebook_id', activeNotebook.id);

    try {
      const response = await fetch('/api/ingest/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Upload failed');
      const data = await response.json();
      
      // Cập nhật lại danh sách documents
      const docRes = await fetch(`/api/notebooks/${activeNotebook.id}/documents`);
      if (docRes.ok) {
        setDocuments(await docRes.json());
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'assistant', content: `❌ Lỗi khi tải tệp: ${err.message}`, citations: [] }]);
    } finally {
      setUploading(false);
      setUploadingDocs(prev => prev.filter(d => d.filename !== file.name));
      e.target.value = null;
    }
  };

  const deleteDocument = async (filename) => {
    if (!activeNotebook) return;
    if (!window.confirm(`Bạn có chắc muốn xóa tài liệu "${filename}"?`)) return;
    
    try {
      const res = await fetch(`/api/notebooks/${activeNotebook.id}/documents?filename=${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.filename !== filename));
      }
    } catch (err) {
      console.error('Error deleting document:', err);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !activeNotebook) return;
    
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      setMessages(prev => [...prev, { role: 'assistant', content: '', citations: [] }]);
      
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg, notebook_id: activeNotebook.id })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        const events = buffer.split('\n\n');
        buffer = events.pop() || "";
        
        for (const event of events) {
          if (event.startsWith("data: ")) {
            const dataStr = event.substring(6);
            try {
              const data = JSON.parse(dataStr);
              
              setMessages(prev => {
                const newMessages = [...prev];
                const lastIndex = newMessages.length - 1;
                
                if (data.type === 'citations') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    citations: data.citations
                  };
                } else if (data.type === 'chunk') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    content: newMessages[lastIndex].content + data.text,
                    status: null
                  };
                } else if (data.type === 'status') {
                  newMessages[lastIndex] = {
                    ...newMessages[lastIndex],
                    status: data.message
                  };
                }
                
                return newMessages;
              });
            } catch (e) {
              console.error("Lỗi parse JSON SSE", e);
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        newMessages[lastIndex] = {
          ...newMessages[lastIndex],
          content: 'Xin lỗi, có lỗi xảy ra khi kết nối tới LLM Engine.'
        };
        return newMessages;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluate = async () => {
    if (!activeNotebook) return;
    setEvaluating(true);
    setEvalResult(null);
    try {
      const formData = new FormData();
      formData.append('notebook_id', activeNotebook.id);
      const res = await fetch('/api/evaluate', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.status === 'success') {
        setEvalResult(data.metrics);
      } else {
        alert("Lỗi đánh giá: " + data.message);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setEvaluating(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!loading && input.trim()) {
        handleSend();
      }
    }
  };

  if (!activeNotebook) return <div className="h-screen w-full flex items-center justify-center bg-[#131314] text-white"><Loader className="animate-spin" size={32} /></div>;

  return (
    <div className="h-screen w-full flex bg-[#131314] text-white overflow-hidden font-sans selection:bg-blue-500/30">
      
      {/* Cột 1: Left Sidebar (Sources) */}
      <div className="w-72 flex-shrink-0 h-full border-r border-white/5 bg-[#131314] flex flex-col p-4 z-10 relative">
        <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 text-gray-400 hover:text-white mb-8 w-fit transition-colors">
          <ArrowLeft size={18} /> Quay lại
        </button>
        <h2 className="font-semibold text-lg mb-4 flex items-center gap-2 text-gray-200">
          <Layers size={18} className="text-blue-400" /> Nguồn dữ liệu
        </h2>
        
        <div className="flex-1 overflow-y-auto scrollbar-hide space-y-3">
          {documents.length === 0 && uploadingDocs.length === 0 ? (
            <div className="text-center text-gray-500 text-sm mt-10">Chưa có dữ liệu nào</div>
          ) : (
            <>
              {uploadingDocs.map((doc, index) => (
                <div key={`up-${index}`} className="p-3 bg-white/5 rounded-xl border border-white/10 flex items-center gap-3 opacity-70">
                  <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0">
                    <Loader size={20} className="animate-spin" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate text-gray-200" title={doc.filename}>{doc.filename}</p>
                    <p className="text-xs text-blue-400 truncate mt-1">Đang nạp...</p>
                  </div>
                </div>
              ))}
              {documents.map((doc, index) => (
                <div key={`doc-${index}`} className="p-3 bg-white/5 rounded-xl border border-white/10 flex items-center justify-between gap-3 group">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400 shrink-0 relative">
                      {doc.filename.includes('http') || doc.filename.includes('YouTube') ? <LinkIcon size={20} /> : <FileText size={20} />}
                      <div className="absolute -bottom-1 -right-1 bg-green-500 rounded-full text-[#131314] p-0.5">
                        <Check size={10} strokeWidth={4} />
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate text-gray-200" title={doc.filename}>{doc.filename}</p>
                      <p className="text-xs text-gray-500 truncate">{new Date(doc.created_at).toLocaleString('vi-VN')}</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => deleteDocument(doc.filename)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded text-gray-400 hover:text-red-400 hover:bg-white/10 transition-all shrink-0"
                    title="Xóa tài liệu"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="pt-4 mt-auto border-t border-white/5">
          <button 
            onClick={() => setShowUrlInput(!showUrlInput)}
            className="w-full bg-white/5 hover:bg-white/10 text-white py-3 rounded-xl flex justify-center items-center gap-2 font-medium transition-colors mb-2 border border-white/10"
          >
            <LinkIcon size={18} /> Thêm Link
          </button>
          <button 
            onClick={() => document.getElementById('file-upload').click()}
            className="w-full bg-white text-black hover:bg-gray-200 py-3 rounded-xl flex justify-center items-center gap-2 font-medium transition-colors shadow-lg"
          >
            <Plus size={18} /> Tải tệp lên
          </button>
        </div>
      </div>

      {/* Cột 2: Center (Chat) */}
      <div className="flex-1 flex flex-col h-full border-r border-white/5 p-4 max-w-4xl mx-auto relative z-10">
      <div className="flex items-center justify-between pb-4 border-b border-white/10 mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <FileText className="text-electric-blue" size={24}/>
            Phòng Chat
          </h2>
          <span className="bg-white/10 text-xs px-2 py-1 rounded-full text-gray-300">
            {activeNotebook?.title || "Chưa chọn Sổ tay"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {evalResult && (
            <div className="flex gap-2 text-xs mr-2">
              <span className="bg-green-500/20 text-green-400 px-2 py-1 rounded border border-green-500/30">
                Chính xác: {evalResult.faithfulness.toFixed(2)}
              </span>
              <span className="bg-blue-500/20 text-blue-400 px-2 py-1 rounded border border-blue-500/30">
                Ngữ cảnh: {evalResult.context_precision.toFixed(2)}
              </span>
            </div>
          )}
          <button 
            onClick={handleEvaluate}
            disabled={evaluating}
            className="text-sm px-3 py-1.5 rounded-lg border border-yellow-500/50 bg-yellow-500/20 text-yellow-500 hover:bg-yellow-500/30 transition-colors disabled:opacity-50 flex items-center gap-1"
            title="Đánh giá chất lượng RAG bằng Ragas"
          >
            {evaluating ? <Loader size={14} className="animate-spin" /> : <Brain size={14} />}
            Đánh giá AI
          </button>
          <button 
            onClick={deleteNotebook}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-400 hover:bg-white/5 transition-colors"
            title="Xóa sổ tay"
          >
            <Trash2 size={18} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-hide flex flex-col gap-6 pb-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-gradient-to-br from-neon-purple to-pink-500' : 'bg-gradient-to-br from-electric-blue to-cyan-400'}`}>
              {msg.role === 'assistant' ? <Bot size={20} className="text-white" /> : <User size={20} className="text-white" />}
            </div>
            <div className={`flex flex-col gap-2 max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div className={`px-5 py-3.5 rounded-2xl text-[15px] leading-relaxed shadow-lg ${
                msg.role === 'user' 
                  ? 'bg-surface border border-white/10 text-white rounded-tr-sm' 
                  : 'glass-panel text-gray-100 rounded-tl-sm'
              }`}>
                {msg.content ? (
                  <div className="relative">
                    {msg.content.split('\n').map((line, i, arr) => (
                      <span key={i}>
                        {line}
                        {msg.role === 'assistant' && loading && idx === messages.length - 1 && i === arr.length - 1 && (
                          <span className="inline-block w-2 h-4 bg-electric-blue animate-pulse ml-1 align-middle rounded-sm shadow-[0_0_8px_rgba(37,99,235,0.8)]"></span>
                        )}
                        <br />
                      </span>
                    ))}
                  </div>
                ) : (
                  msg.role === 'assistant' && loading && idx === messages.length - 1 && (
                    <div className="flex flex-col gap-3">
                      <span className="flex gap-1 items-center h-5">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></span>
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.4s'}}></span>
                      </span>
                      {msg.status && (
                        <div className="flex items-center gap-2 text-xs text-electric-blue font-medium animate-pulse">
                          <Loader size={12} className="animate-spin" />
                          {msg.status}
                        </div>
                      )}
                    </div>
                  )
                )}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {msg.citations.map((cit, cidx) => (
                    <div 
                      key={cidx} 
                      onClick={() => setSelectedCitation(cit)}
                      className="flex items-center gap-1.5 text-xs bg-electric-blue/10 border border-electric-blue/30 text-electric-blue px-2.5 py-1 rounded-full cursor-pointer hover:bg-electric-blue/20 transition-colors"
                    >
                      <span className="font-semibold">{cit.marker}</span>
                      <ChevronRight size={12} className="opacity-50" />
                      <span className="truncate max-w-[150px] opacity-80">{cit.filename}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="pt-4">
        <div className="glass-panel p-2 flex items-end gap-2 rounded-2xl relative group focus-within:shadow-[0_0_20px_rgba(37,99,235,0.2)] focus-within:border-electric-blue/40 transition-all duration-300">
          
          <div className="relative">
            {showUrlInput && (
              <div className="absolute bottom-full left-0 mb-2 bg-surface border border-white/10 p-2 rounded-lg shadow-xl flex gap-2 z-20 w-80">
                <input 
                  type="text" 
                  value={urlInputValue}
                  onChange={(e) => setUrlInputValue(e.target.value)}
                  placeholder="Dán link YouTube / Website..." 
                  className="flex-1 bg-black/30 text-sm px-3 py-2 rounded-md outline-none text-white border border-white/10 focus:border-electric-blue"
                  onKeyDown={(e) => e.key === 'Enter' && handleUrlSubmit()}
                />
                <button 
                  onClick={handleUrlSubmit}
                  className="bg-electric-blue px-3 rounded-md text-white hover:bg-blue-600 transition-colors"
                >
                  <Check size={16}/>
                </button>
              </div>
            )}
            <button 
              onClick={() => setShowUrlInput(!showUrlInput)}
              className="p-3 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-all"
              title="Nhập Link Website hoặc YouTube"
            >
              <LinkIcon size={20} />
            </button>
          </div>
          
          <button 
            onClick={() => document.getElementById('file-upload').click()}
            className="p-3 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-xl transition-all"
            title="Tải lên PDF/Doc/Audio"
          >
            <Paperclip size={20} />
          </button>
          <input 
            type="file" 
            id="file-upload" 
            className="hidden" 
            onChange={handleFileUpload}
            accept=".pdf,.docx,.txt,.md,.csv,.png,.jpg,.jpeg,.mp3,.wav,.m4a"
          />

          <textarea 
            className="flex-1 bg-transparent border-none px-2 py-3 text-[15px] text-white focus:outline-none focus:ring-0 resize-none min-h-[50px] max-h-[150px] scrollbar-hide"
            placeholder="Hỏi bất cứ điều gì về tài liệu..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button 
            className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
              input.trim() && !loading 
                ? 'bg-electric-blue text-white hover:bg-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.4)]' 
                : 'bg-white/5 text-gray-500 cursor-not-allowed'
            }`}
            onClick={handleSend} 
            disabled={!input.trim() || loading}
          >
            <Send size={20} className={input.trim() && !loading ? 'translate-x-0.5 -translate-y-0.5' : ''} />
          </button>
        </div>
        <div className="text-center mt-3 text-xs text-gray-500">
          NotebookLM Mini có thể đưa ra thông tin không chính xác. Hãy luôn kiểm tra lại nguồn trích dẫn.
        </div>
      </div>
      </div>

      <div className="w-80 lg:w-96 flex-shrink-0 h-full p-4 overflow-y-auto scrollbar-hide bg-[#131314] flex flex-col gap-6 border-l border-white/5">
        <div className="glass-panel p-5 rounded-2xl border border-white/10">
          <h3 className="text-lg font-bold text-electric-blue mb-3 flex items-center gap-2">
            <BookOpen size={20} /> Cẩm Nang Học Tập
          </h3>
          
          {documents.length === 0 ? (
            <div className="text-gray-400 text-sm mt-4 text-center">
              Vui lòng tải lên tài liệu để tạo Cẩm nang học tập.
            </div>
          ) : !studyGuide ? (
            <div className="flex flex-col items-center justify-center py-6 text-gray-400 gap-3">
              <Loader className="animate-spin text-electric-blue" size={24} />
              <span className="text-sm">Đang phân tích tài liệu...</span>
            </div>
          ) : (
            <div className="space-y-4 text-sm mt-4">
              <div>
                <h4 className="font-semibold text-gray-300 mb-1">Tóm tắt:</h4>
                <p className="text-gray-400 leading-relaxed">{studyGuide.summary}</p>
              </div>
              <div className="pt-2 border-t border-white/10">
                <h4 className="font-semibold text-gray-300 mb-1">Câu hỏi thường gặp:</h4>
                <p className="text-gray-400 whitespace-pre-wrap">{studyGuide.faq}</p>
              </div>

              <div className="pt-4 flex gap-2 border-t border-white/10">
                <button 
                  onClick={() => setShowQuiz(true)}
                  disabled={!studyGuide.quiz || studyGuide.quiz.length === 0}
                  className="flex-1 bg-white/5 hover:bg-electric-blue/20 text-electric-blue border border-electric-blue/30 py-2 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <Brain size={16} /> Quiz
                </button>
                <button 
                  onClick={() => { setShowFlashcards(true); setCurrentFlashcard(0); setFlashcardFlipped(false); }}
                  disabled={!studyGuide.flashcards || studyGuide.flashcards.length === 0}
                  className="flex-1 bg-white/5 hover:bg-neon-purple/20 text-neon-purple border border-neon-purple/30 py-2 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <Layers size={16} /> Thẻ từ
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="glass-panel p-5 rounded-2xl border border-white/10">
          <h3 className="text-lg font-bold text-neon-purple mb-3 flex items-center gap-2">
            <Headphones size={20} /> Trò Chuyện AI (Podcast)
          </h3>
          
          {!audioUrl ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-gray-400">Tạo bản thu âm trò chuyện giữa 2 MC ảo dựa trên tài liệu.</p>
              <button 
                onClick={generatePodcast}
                disabled={podcastGenerating || !studyGuide}
                className="w-full bg-gradient-to-r from-electric-blue to-neon-purple hover:opacity-90 text-white font-medium py-2 rounded-xl transition-all disabled:opacity-50 flex justify-center items-center gap-2"
              >
                {podcastGenerating ? <RefreshCw className="animate-spin" size={18} /> : <Headphones size={18} />}
                {podcastGenerating ? "Đang tạo (vui lòng đợi)..." : "Tạo Podcast"}
              </button>
            </div>
          ) : (
             <div className="mt-2">
               <audio controls className="w-full h-10 rounded outline-none" src={audioUrl} />
             </div>
          )}
        </div>
      </div>

      {showQuiz && studyGuide?.quiz && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="glass-panel w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl border border-electric-blue/30 overflow-hidden shadow-2xl">
            <div className="p-4 border-b border-white/10 flex justify-between items-center bg-electric-blue/10">
              <h2 className="text-xl font-bold flex items-center gap-2"><Brain className="text-electric-blue" /> Trắc nghiệm kiến thức</h2>
              <button onClick={() => {setShowQuiz(false); setQuizAnswers({}); setQuizSubmitted(false);}} className="text-gray-400 hover:text-white"><X size={24}/></button>
            </div>
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {studyGuide.quiz.map((q, idx) => (
                <div key={idx} className="bg-white/5 p-4 rounded-xl border border-white/10">
                  <p className="font-semibold text-lg mb-3">{idx + 1}. {q.question}</p>
                  <div className="space-y-2">
                    {q.options.map((opt, oIdx) => {
                      const isSelected = quizAnswers[idx] === oIdx;
                      const isCorrect = q.answer === oIdx;
                      let btnClass = "w-full text-left p-3 rounded-lg border transition-all ";
                      
                      if (!quizSubmitted) {
                        btnClass += isSelected ? "border-electric-blue bg-electric-blue/20 text-white" : "border-white/10 hover:bg-white/10 text-gray-300";
                      } else {
                        if (isCorrect) btnClass += "border-green-500 bg-green-500/20 text-white";
                        else if (isSelected && !isCorrect) btnClass += "border-red-500 bg-red-500/20 text-white";
                        else btnClass += "border-white/5 text-gray-500 opacity-50";
                      }

                      return (
                        <button 
                          key={oIdx} 
                          disabled={quizSubmitted}
                          onClick={() => setQuizAnswers({...quizAnswers, [idx]: oIdx})}
                          className={btnClass}
                        >
                          <div className="flex justify-between items-center">
                            <span>{opt}</span>
                            {quizSubmitted && isCorrect && <Check size={18} className="text-green-500" />}
                            {quizSubmitted && isSelected && !isCorrect && <XCircle size={18} className="text-red-500" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-white/10 bg-black/20 flex justify-end">
              {!quizSubmitted ? (
                <button 
                  onClick={() => setQuizSubmitted(true)}
                  disabled={Object.keys(quizAnswers).length !== studyGuide.quiz.length}
                  className="bg-electric-blue hover:bg-blue-600 text-white px-6 py-2 rounded-xl font-medium disabled:opacity-50"
                >
                  Nộp bài
                </button>
              ) : (
                <button 
                  onClick={() => {setQuizAnswers({}); setQuizSubmitted(false);}}
                  className="bg-white/10 hover:bg-white/20 text-white px-6 py-2 rounded-xl font-medium"
                >
                  Làm lại
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {showFlashcards && studyGuide?.flashcards && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fade-in">
          <div className="w-full max-w-lg flex flex-col items-center">
            <div className="w-full flex justify-end mb-4">
               <button onClick={() => setShowFlashcards(false)} className="text-gray-400 hover:text-white bg-black/50 p-2 rounded-full backdrop-blur-md"><X size={24}/></button>
            </div>
            
            <div 
              className="w-full h-80 relative perspective-1000 cursor-pointer" 
              onClick={() => setFlashcardFlipped(!flashcardFlipped)}
            >
              <div className={`w-full h-full absolute transition-transform duration-500 transform-style-3d ${flashcardFlipped ? 'rotate-y-180' : ''}`}>
                {/* Front */}
                <div className="absolute inset-0 backface-hidden glass-panel border border-neon-purple/30 rounded-2xl flex items-center justify-center p-8 text-center shadow-[0_0_30px_rgba(168,85,247,0.2)]">
                  <div>
                    <div className="text-neon-purple/50 text-sm font-bold tracking-widest uppercase mb-4">Khái niệm</div>
                    <h2 className="text-3xl font-bold text-white">{studyGuide.flashcards[currentFlashcard].front}</h2>
                    <div className="text-gray-500 text-xs mt-8 absolute bottom-4 left-0 w-full text-center">Chạm để lật mặt sau</div>
                  </div>
                </div>
                {/* Back */}
                <div className="absolute inset-0 backface-hidden glass-panel border border-electric-blue/30 rounded-2xl flex items-center justify-center p-8 text-center rotate-y-180 shadow-[0_0_30px_rgba(37,99,235,0.2)] bg-gradient-to-br from-black/80 to-electric-blue/10">
                  <div>
                    <div className="text-electric-blue/50 text-sm font-bold tracking-widest uppercase mb-4">Định nghĩa</div>
                    <p className="text-lg text-gray-200 leading-relaxed">{studyGuide.flashcards[currentFlashcard].back}</p>
                    <div className="text-gray-500 text-xs mt-8 absolute bottom-4 left-0 w-full text-center">Chạm để quay lại</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="mt-8 flex items-center gap-6">
              <button 
                onClick={() => {setCurrentFlashcard(Math.max(0, currentFlashcard - 1)); setFlashcardFlipped(false);}}
                disabled={currentFlashcard === 0}
                className="bg-white/10 hover:bg-white/20 p-3 rounded-full disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={24} className="rotate-180" />
              </button>
              <span className="font-mono text-gray-400">
                {currentFlashcard + 1} / {studyGuide.flashcards.length}
              </span>
              <button 
                onClick={() => {setCurrentFlashcard(Math.min(studyGuide.flashcards.length - 1, currentFlashcard + 1)); setFlashcardFlipped(false);}}
                disabled={currentFlashcard === studyGuide.flashcards.length - 1}
                className="bg-white/10 hover:bg-white/20 p-3 rounded-full disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={24} />
              </button>
            </div>

          </div>
        </div>
      )}

      {/* Citation Preview Modal */}
      {selectedCitation && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm animate-fade-in">
          <div className="bg-[#1C1F26] border border-white/10 rounded-2xl p-6 max-w-2xl w-full shadow-2xl flex flex-col max-h-[80vh] text-left">
            <div className="flex justify-between items-center mb-4 pb-3 border-b border-white/10">
              <h3 className="text-lg font-semibold text-blue-400">
                Chi tiết trích dẫn {selectedCitation.marker}
              </h3>
              <button 
                onClick={() => setSelectedCitation(null)}
                className="text-gray-400 hover:text-white transition-colors text-lg"
              >
                ✕
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto pr-2 text-sm text-gray-300 space-y-4">
              <div>
                <span className="text-xs text-gray-500 font-medium">Nguồn tài liệu:</span>
                <p className="text-white font-medium mt-0.5 break-all">{selectedCitation.filename}</p>
              </div>
              
              <div>
                <span className="text-xs text-gray-500 font-medium">Nội dung trích dẫn:</span>
                <div className="bg-black/30 border border-white/5 rounded-xl p-4 mt-1 font-sans text-gray-200 leading-relaxed whitespace-pre-wrap max-h-[40vh] overflow-y-auto">
                  {selectedCitation.content || "Không có nội dung chi tiết."}
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <button 
                onClick={() => setSelectedCitation(null)}
                className="px-5 py-2 rounded-full text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default Studio;
