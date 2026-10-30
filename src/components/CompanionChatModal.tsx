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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import MarkdownText from './MarkdownText';
import { PersonaItem } from '../services/personaService';
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

export default function CompanionChatModal({
  visible,
  persona,
  onClose,
}: CompanionChatModalProps) {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState<string>('');
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const flatListRef = useRef<FlatList>(null);

  // Initialize with persona's customized greeting
  useEffect(() => {
    if (!visible || !persona) {
      setMessages([]);
      return;
    }

    const initialGreeting = persona.greeting || `*smiles gently* Hello! I am ${persona.name}. How are you today?`;
    setMessages([
      {
        id: 'msg-greeting',
        sender: 'bot',
        text: initialGreeting,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  }, [visible, persona]);

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !persona || isTyping) return;

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

    try {
      const res = await fetch(`${API_CONFIG.baseUrl}/memory/chat/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(user?.token ? { Authorization: `Bearer ${user.token}` } : {}),
        },
        body: JSON.stringify({
          message: text,
          persona_id: persona.id,
          persona_name: persona.name,
          memory_prompt: persona.memory_prompt,
        }),
      });

      let replyText = '';
      if (res.ok) {
        const data = await res.json();
        replyText = data.reply || data.generation || '';
      }

      if (!replyText) {
        // In-character thoughtful fallback
        replyText = `*listens attentively and nods* I hear you deeply. With everything you just shared, I am right here with you.`;
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
        text: `*offers a gentle, supportive smile* I am listening closely. Tell me more about what you are thinking.`,
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

  if (!persona) return null;
  const borderColor = persona.border_color || '#F43F5E';

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
                {persona.image_url ? (
                  <Image source={{ uri: persona.image_url }} style={styles.headerAvatarImg} />
                ) : (
                  <View style={[styles.headerAvatarImg, { backgroundColor: borderColor }]}>
                    <Text style={styles.headerAvatarLetter}>
                      {persona.name.charAt(0).toUpperCase()}
                    </Text>
                  </View>
                )}
              </View>

              <View style={styles.headerTextCol}>
                <Text style={styles.headerBotName}>{persona.name}</Text>
                <Text style={styles.headerStatusText}>Online · Amour Companion</Text>
              </View>
            </View>

            <View style={{ width: 36 }} />
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
                      {persona.image_url ? (
                        <Image source={{ uri: persona.image_url }} style={styles.miniAvatarImg} />
                      ) : (
                        <View style={[styles.miniAvatarImg, { backgroundColor: borderColor }]}>
                          <Text style={styles.miniAvatarLetter}>{persona.name.charAt(0)}</Text>
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
                    <Text style={styles.typingText}>{persona.name} is thinking...</Text>
                  </View>
                </View>
              ) : undefined
            }
          />

          {/* Bottom Chat Input */}
          <View style={styles.inputBar}>
            <TextInput
              style={styles.chatTextInput}
              placeholder={`Message ${persona.name}...`}
              placeholderTextColor="#6B7280"
              value={inputText}
              onChangeText={setInputText}
              multiline
              maxLength={1000}
            />

            <TouchableOpacity
              style={[
                styles.sendBtn,
                (!inputText.trim() || isTyping) && styles.sendBtnDisabled,
              ]}
              onPress={handleSend}
              disabled={!inputText.trim() || isTyping}
              activeOpacity={0.7}
            >
              <SendIcon size={18} color={inputText.trim() ? borderColor : '#4B5563'} />
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
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
    height: 58,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1A1A24',
    backgroundColor: '#09090D',
  },
  closeBtn: {
    padding: 6,
  },
  headerAvatarCol: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    marginLeft: 8,
  },
  headerSquircle: {
    width: 38,
    height: 38,
    borderRadius: 14,
    borderWidth: 1.5,
    overflow: 'hidden',
    backgroundColor: '#1E1E2A',
  },
  headerAvatarImg: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerAvatarLetter: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 16,
  },
  headerTextCol: {
    flex: 1,
  },
  headerBotName: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },
  headerStatusText: {
    color: '#10B981',
    fontSize: 11,
    fontWeight: '500',
  },

  messagesList: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
  },
  messageBubbleRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginBottom: 8,
  },
  userBubbleRow: {
    justifyContent: 'flex-end',
  },
  botBubbleRow: {
    justifyContent: 'flex-start',
  },

  miniAvatarSquircle: {
    width: 28,
    height: 28,
    borderRadius: 10,
    borderWidth: 1,
    overflow: 'hidden',
    backgroundColor: '#1E1E2A',
  },
  miniAvatarImg: {
    width: '100%',
    height: '100%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  miniAvatarLetter: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
  },

  bubbleBox: {
    maxWidth: '82%',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 16,
  },
  userBubbleBox: {
    backgroundColor: '#2A1820',
    borderBottomRightRadius: 4,
    borderWidth: 1,
    borderColor: '#4A2834',
  },
  botBubbleBox: {
    backgroundColor: '#12121C',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#1F1F2E',
  },
  userBubbleText: {
    color: '#FFFFFF',
    fontSize: 14,
    lineHeight: 20,
  },
  botBubbleText: {
    color: '#E5E7EB',
    fontSize: 14,
    lineHeight: 20,
  },
  bubbleTimestamp: {
    color: '#6B7280',
    fontSize: 10,
    marginTop: 4,
    alignSelf: 'flex-end',
  },

  typingIndicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 6,
  },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: '#12121C',
    borderRadius: 14,
  },
  typingText: {
    color: '#9CA3AF',
    fontSize: 12,
  },

  inputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: '#161622',
    backgroundColor: '#09090D',
    gap: 10,
  },
  chatTextInput: {
    flex: 1,
    color: '#FFFFFF',
    fontSize: 14,
    maxHeight: 100,
    paddingVertical: 8,
    paddingHorizontal: 14,
    backgroundColor: '#14141E',
    borderRadius: 20,
  },
  sendBtn: {
    padding: 8,
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
});
