import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  FlatList,
  TextInput,
  TouchableOpacity,
  Image,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import MarkdownText from './MarkdownText';
import { PersonaItem, updatePersonaMemory } from '../services/personaService';
import { API_CONFIG } from '../constants/authConfig';
import { useAuth } from '../context/AuthContext';

function CloseIcon({ size = 20, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M18 6L6 18M6 6l12 12" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function SendIcon({ size = 18, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </Svg>
  );
}

function BrainIcon({ size = 18, color = '#F43F5E' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M9.5 2A2.5 2.5 0 0 0 7 4.5V5A3 3 0 0 0 4 8v1a3 3 0 0 0-1 2.25c0 1.25.75 2.3 1.83 2.75A3 3 0 0 0 4 16v1a3 3 0 0 0 3 3h.5A2.5 2.5 0 0 0 10 22h.5a2.5 2.5 0 0 0 2.5-2.5V19a2.5 2.5 0 0 0-2.5-2.5H10v-3h1.5A2.5 2.5 0 0 0 14 11V8.5A2.5 2.5 0 0 0 11.5 6H10V4.5A2.5 2.5 0 0 0 7.5 2h2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M14.5 2A2.5 2.5 0 0 1 17 4.5V5a3 3 0 0 1 3 3v1a3 3 0 0 1 1 2.25c0 1.25-.75 2.3-1.83 2.75A3 3 0 0 1 20 16v1a3 3 0 0 1-3 3h-.5A2.5 2.5 0 0 1 14 22h-.5a2.5 2.5 0 0 1-2.5-2.5V19a2.5 2.5 0 0 1 2.5-2.5H14v-3h-1.5A2.5 2.5 0 0 1 10 11V8.5A2.5 2.5 0 0 1 12.5 6H14V4.5A2.5 2.5 0 0 1 16.5 2h-2z"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
}

interface CompanionChatModalProps {
  visible: boolean;
  persona: PersonaItem | null;
  onClose: () => void;
}

const CANDIDATE_URLS = [
  'http://127.0.0.1:8000/api',
  'http://192.168.1.4:8000/api',
  API_CONFIG.baseUrl,
  'http://10.104.217.217:8000/api',
  'http://192.168.1.2:8000/api',
];

async function tryChatFetch(payload: any, token?: string): Promise<{ reply?: string } | null> {
  for (const base of CANDIDATE_URLS) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 12000);
      const res = await fetch(`${base}/memory/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // try next candidate endpoint
    }
  }
  return null;
}

export default function CompanionChatModal({
  visible,
  persona,
  onClose,
}: CompanionChatModalProps) {
  const { user } = useAuth();
  const [activePersona, setActivePersona] = useState<PersonaItem | null>(persona);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [showMemoryModal, setShowMemoryModal] = useState<boolean>(false);
  const [memoryInput, setMemoryInput] = useState<string>('');
  const [greetingInput, setGreetingInput] = useState<string>('');
  const [isSavingMemory, setIsSavingMemory] = useState<boolean>(false);
  const flatListRef = useRef<FlatList>(null);

  // Initialize with persona's customized greeting (opening script)
  useEffect(() => {
    if (!visible || !persona) {
      setMessages([]);
      return;
    }

    setActivePersona(persona);
    setMemoryInput(persona.memory_prompt || '');
    setGreetingInput(persona.greeting || '');

    const initialGreeting = persona.greeting || `Hello! I am ${persona.name}. How are you today?`;
    setMessages([
      {
        id: 'msg-greeting',
        sender: 'bot',
        text: initialGreeting,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, [visible, persona]);

  const handleSaveMemoryModal = async () => {
    if (!activePersona) return;
    setIsSavingMemory(true);
    try {
      const updated = await updatePersonaMemory(
        activePersona.id,
        {
          greeting: greetingInput.trim(),
          memory_prompt: memoryInput.trim(),
        },
        user?.id
      );
      if (updated) {
        setActivePersona(updated);
        setShowMemoryModal(false);
      }
    } catch (e) {
      console.warn('[CompanionChatModal] Error saving memory:', e);
    } finally {
      setIsSavingMemory(false);
    }
  };

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !activePersona || isTyping) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsTyping(true);

    setTimeout(() => {
      flatListRef.current?.scrollToEnd({ animated: true });
    }, 100);

    const clientTime = new Date().toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    const clientTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata';

    const payload = {
      message: text,
      persona_id: activePersona.id,
      persona_name: activePersona.name,
      greeting: activePersona.greeting,
      memory_prompt: activePersona.memory_prompt,
      client_time: clientTime,
      client_timezone: clientTimezone,
      user_id: user?.id,
    };

    try {
      const data = await tryChatFetch(payload, user?.token);
      let replyText = data?.reply || '';

      if (!replyText) {
        replyText = "I hear you. Tell me more about what is on your mind.";
      }

      const botReply: ChatMessage = {
        id: `bot-${Date.now()}`,
        sender: 'bot',
        text: replyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botReply]);
    } catch (err) {
      const fallbackReply: ChatMessage = {
        id: `bot-fallback-${Date.now()}`,
        sender: 'bot',
        text: "I am listening closely. Tell me more about what you are thinking.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, fallbackReply]);
    } finally {
      setIsTyping(false);
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  };

  if (!activePersona) return null;
  const borderColor = activePersona.border_color || '#F43F5E';

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={false}
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
        <KeyboardAvoidingView
          style={styles.keyboardContainer}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 20 : 0}
        >
          {/* Top Header */}
          <View style={styles.topHeader}>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn} activeOpacity={0.7}>
              <CloseIcon size={20} color="#FFFFFF" />
            </TouchableOpacity>

            <View style={styles.headerAvatarCol}>
              <View style={[styles.headerSquircle, { borderColor }]}>
                {activePersona.image_url ? (
                  <Image source={{ uri: activePersona.image_url }} style={styles.headerAvatarImg} />
                ) : (
                  <View style={[styles.headerAvatarImg, { backgroundColor: borderColor }]}>
                    <Text style={styles.headerAvatarLetter}>
                      {activePersona.name.charAt(0).toUpperCase()}
                    </Text>
                  </View>
                )}
              </View>

              <View style={styles.headerTextCol}>
                <Text style={styles.headerBotName}>{activePersona.name}</Text>
                <Text style={styles.headerStatusText}>Online · Reeve Memory</Text>
              </View>
            </View>

            <TouchableOpacity
              onPress={() => setShowMemoryModal(true)}
              style={styles.memoryHeaderBtn}
              activeOpacity={0.7}
              accessibilityLabel="View persona memory"
            >
              <BrainIcon size={18} color={borderColor} />
            </TouchableOpacity>
          </View>

          {/* Messages Flow */}
          <FlatList
            ref={flatListRef}
            data={messages}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.messagesList}
            renderItem={({ item }) => {
              const isUser = item.sender === 'user';
              return (
                <View
                  style={[
                    styles.messageBubbleRow,
                    isUser ? styles.userBubbleRow : styles.botBubbleRow,
                  ]}
                >
                  {!isUser && (
                    <View style={[styles.miniAvatarSquircle, { borderColor }]}>
                      {activePersona.image_url ? (
                        <Image source={{ uri: activePersona.image_url }} style={styles.miniAvatarImg} />
                      ) : (
                        <View style={[styles.miniAvatarImg, { backgroundColor: borderColor }]}>
                          <Text style={styles.miniAvatarLetter}>{activePersona.name.charAt(0)}</Text>
                        </View>
                      )}
                    </View>
                  )}

                  <View
                    style={[
                      styles.bubbleBox,
                      isUser ? styles.userBubbleBox : styles.botBubbleBox,
                      !isUser && { borderLeftColor: borderColor, borderLeftWidth: 2 },
                    ]}
                  >
                    <MarkdownText
                      content={item.text}
                      style={isUser ? styles.userBubbleText : styles.botBubbleText}
                    />
                    <Text style={styles.bubbleTimestamp}>{item.timestamp}</Text>
                  </View>
                </View>
              );
            }}
            ListFooterComponent={
              isTyping ? (
                <View style={styles.typingIndicatorRow}>
                  <View style={[styles.miniAvatarSquircle, { borderColor }]}>
                    <View style={[styles.miniAvatarImg, { backgroundColor: borderColor }]} />
                  </View>
                  <View style={styles.typingBubble}>
                    <ActivityIndicator size="small" color={borderColor} />
                    <Text style={styles.typingText}>{activePersona.name} is typing...</Text>
                  </View>
                </View>
              ) : undefined
            }
          />

          {/* Bottom Chat Input */}
          <View style={styles.inputBar}>
            <TextInput
              style={styles.chatTextInput}
              placeholder={`Message ${activePersona.name}...`}
              placeholderTextColor="#6B7280"
              value={inputText}
              onChangeText={setInputText}
              multiline
              maxLength={1000}
            />

            <TouchableOpacity
              style={[
                styles.sendBtn,
                { backgroundColor: inputText.trim() ? borderColor : '#1E1E28' },
              ]}
              onPress={handleSend}
              disabled={!inputText.trim() || isTyping}
              activeOpacity={0.8}
            >
              <SendIcon size={16} color={inputText.trim() ? '#FFFFFF' : '#4B5563'} />
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>

        {/* Live In-Chat Memory Tuning Sheet */}
        <Modal
          visible={showMemoryModal}
          animationType="fade"
          transparent={true}
          onRequestClose={() => setShowMemoryModal(false)}
        >
          <View style={styles.modalBackdrop}>
            <View style={styles.modalSheetCard}>
              <View style={styles.modalSheetHeader}>
                <View style={styles.modalSheetTitleRow}>
                  <BrainIcon size={18} color={borderColor} />
                  <Text style={styles.modalSheetTitle}>Companion Memory (Reeve)</Text>
                </View>
                <TouchableOpacity onPress={() => setShowMemoryModal(false)} style={styles.sheetCloseBtn}>
                  <CloseIcon size={18} color="#FFFFFF" />
                </TouchableOpacity>
              </View>

              <ScrollView style={styles.modalSheetBody} showsVerticalScrollIndicator={false}>
                <Text style={styles.sheetFieldLabel}>FIRST MESSAGE / OPENING SCRIPT</Text>
                <TextInput
                  style={styles.sheetInput}
                  value={greetingInput}
                  onChangeText={setGreetingInput}
                  placeholder="First message opening script..."
                  placeholderTextColor="#6B7280"
                  multiline
                  numberOfLines={2}
                />

                <Text style={[styles.sheetFieldLabel, { marginTop: 14 }]}>
                  PERSONALITY & STORY (REEVE GRAPH)
                </Text>
                <TextInput
                  style={[styles.sheetInput, { minHeight: 90 }]}
                  value={memoryInput}
                  onChangeText={setMemoryInput}
                  placeholder="Backstory and memory..."
                  placeholderTextColor="#6B7280"
                  multiline
                  numberOfLines={4}
                />
                <Text style={styles.sheetSubHint}>
                  100% stored into Reeve. Changes take effect on the very next message.
                </Text>

                <View style={styles.sheetActionRow}>
                  <TouchableOpacity
                    style={styles.sheetCancelBtn}
                    onPress={() => setShowMemoryModal(false)}
                  >
                    <Text style={styles.sheetCancelText}>Cancel</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.sheetSaveBtn, { backgroundColor: borderColor }]}
                    onPress={handleSaveMemoryModal}
                    disabled={isSavingMemory}
                  >
                    {isSavingMemory ? (
                      <ActivityIndicator size="small" color="#FFFFFF" />
                    ) : (
                      <Text style={styles.sheetSaveText}>Save to Reeve</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </ScrollView>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#000000',
  },
  keyboardContainer: {
    flex: 1,
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#16161D',
  },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#161620',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#262634',
  },
  headerAvatarCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerSquircle: {
    width: 40,
    height: 40,
    borderRadius: 12,
    borderWidth: 1.5,
    overflow: 'hidden',
  },
  headerAvatarImg: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerAvatarLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
    color: '#FFFFFF',
  },
  headerTextCol: {
    justifyContent: 'center',
  },
  headerBotName: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 17,
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  headerStatusText: {
    fontSize: 11,
    color: '#10B981',
    marginTop: 2,
  },
  memoryHeaderBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#161620',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#262634',
  },
  messagesList: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 14,
  },
  messageBubbleRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    maxWidth: '85%',
  },
  userBubbleRow: {
    alignSelf: 'flex-end',
  },
  botBubbleRow: {
    alignSelf: 'flex-start',
  },
  miniAvatarSquircle: {
    width: 28,
    height: 28,
    borderRadius: 8,
    borderWidth: 1.2,
    overflow: 'hidden',
  },
  miniAvatarImg: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  miniAvatarLetter: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 12,
    color: '#FFFFFF',
  },
  bubbleBox: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 16,
  },
  userBubbleBox: {
    backgroundColor: '#1E1E2C',
    borderBottomRightRadius: 4,
  },
  botBubbleBox: {
    backgroundColor: '#12121A',
    borderBottomLeftRadius: 4,
  },
  userBubbleText: {
    fontSize: 14.5,
    color: '#FFFFFF',
    lineHeight: 21,
  },
  botBubbleText: {
    fontSize: 14.5,
    color: '#E5E7EB',
    lineHeight: 21,
  },
  bubbleTimestamp: {
    fontSize: 10,
    color: '#6B7280',
    alignSelf: 'flex-end',
    marginTop: 4,
  },
  typingIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 6,
  },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#12121A',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
  },
  typingText: {
    fontSize: 12,
    color: '#9CA3AF',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#16161D',
    backgroundColor: '#000000',
  },
  chatTextInput: {
    flex: 1,
    backgroundColor: '#12121A',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    fontSize: 14,
    color: '#FFFFFF',
    maxHeight: 100,
    borderWidth: 1,
    borderColor: '#222230',
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  modalSheetCard: {
    backgroundColor: '#101018',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#262636',
    padding: 18,
    maxHeight: '80%',
  },
  modalSheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  modalSheetTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modalSheetTitle: {
    fontFamily: 'ChangaOne-Regular',
    fontSize: 16,
    color: '#FFFFFF',
  },
  sheetCloseBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: '#1C1C28',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalSheetBody: {
    maxHeight: 350,
  },
  sheetFieldLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#9CA3AF',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  sheetInput: {
    backgroundColor: '#161622',
    borderRadius: 12,
    padding: 12,
    color: '#FFFFFF',
    fontSize: 13.5,
    borderWidth: 1,
    borderColor: '#262636',
    textAlignVertical: 'top',
  },
  sheetSubHint: {
    fontSize: 11,
    color: '#60A5FA',
    marginTop: 6,
    fontStyle: 'italic',
  },
  sheetActionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 18,
    marginBottom: 8,
  },
  sheetCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    backgroundColor: '#1C1C28',
  },
  sheetCancelText: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  sheetSaveBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  sheetSaveText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
});
