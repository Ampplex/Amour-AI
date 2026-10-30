import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  Image,
  Dimensions,
  ActivityIndicator,
  RefreshControl,
  Platform,
  Animated,
  Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Svg, { Path, Circle } from 'react-native-svg';
import AmourLogoVector from '../../components/AmourLogoVector';
import PersonaDetailModal from '../../components/PersonaDetailModal';
import PublisherProfileModal from '../../components/PublisherProfileModal';
import CompanionChatModal from '../../components/CompanionChatModal';
import { useAuth } from '../../context/AuthContext';
import { showAlert } from '../../context/AlertContext';
import {
  FeedPersonaItem,
  fetchFeedPage,
  togglePersonaLike,
  togglePublisherFollow,
  formatCount,
} from '../../services/feedService';
import { PersonaItem } from '../../services/personaService';

const { width } = Dimensions.get('window');
const MEDIA_HEIGHT = Math.min(width, 420);

// Clean Minimalist Vector Icons - Strictly Zero Emojis
function HeartIcon({ size = 22, filled = false, color = '#FFFFFF' }: { size?: number; filled?: boolean; color?: string }) {
  if (filled) {
    return (
      <Svg width={size} height={size} viewBox="0 0 24 24" fill="#F43F5E">
        <Path
          d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
        />
      </Svg>
    );
  }
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12.1 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54l-1.35 1.31z"
        stroke={color}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function FloatingChatBubble({ size = 18, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <Path
        d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"
      />
    </Svg>
  );
}

function ShareIcon({ size = 21, color = '#FFFFFF' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M22 2L11 13"
        stroke={color}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M22 2L15 22L11 13L2 9L22 2Z"
        stroke={color}
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// Single Feed Post Item with Instagram/Chai layout
const FeedPostCard = React.memo(({
  item,
  onPressProfile,
  onPressPublisher,
  onInitiateChat,
  onToggleLike,
  onToggleFollow,
  onSharePersona,
}: {
  item: FeedPersonaItem;
  onPressProfile: (persona: FeedPersonaItem) => void;
  onPressPublisher: (handle: string, name: string, avatar: string) => void;
  onInitiateChat: (persona: FeedPersonaItem) => void;
  onToggleLike: (id: string, currentLiked: boolean) => void;
  onToggleFollow: (handle: string, currentFollowing: boolean) => void;
  onSharePersona: (persona: FeedPersonaItem) => void;
}) => {
  const [expanded, setExpanded] = useState(false);
  const lastTapRef = useRef<number>(0);
  const heartScaleAnim = useRef(new Animated.Value(0)).current;
  const heartOpacityAnim = useRef(new Animated.Value(0)).current;

  // Double-tap on image to trigger instant like with animated heart pop
  const handleMediaPress = () => {
    const now = Date.now();
    const DOUBLE_TAP_DELAY = 300;
    if (now - lastTapRef.current < DOUBLE_TAP_DELAY) {
      // Double tap detected
      if (!item.is_liked) {
        onToggleLike(item.id, false);
      }
      triggerHeartPopAnimation();
    } else {
      // Single tap -> Open details modal
      lastTapRef.current = now;
      setTimeout(() => {
        if (Date.now() - lastTapRef.current >= DOUBLE_TAP_DELAY) {
          onPressProfile(item);
        }
      }, DOUBLE_TAP_DELAY);
    }
  };

  const triggerHeartPopAnimation = () => {
    heartScaleAnim.setValue(0.3);
    heartOpacityAnim.setValue(1);
    Animated.parallel([
      Animated.spring(heartScaleAnim, {
        toValue: 1.3,
        friction: 3,
        useNativeDriver: true,
      }),
      Animated.sequence([
        Animated.delay(400),
        Animated.timing(heartOpacityAnim, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }),
      ]),
    ]).start();
  };

  const borderColor = item.border_color || '#F43F5E';
  const publisherName = item.publisher_name || item.creator_name || 'Creator';
  const publisherHandle = item.publisher_handle || `@${publisherName.toLowerCase().replace(/\s+/g, '_')}`;
  const publisherInitial = publisherName.charAt(0).toUpperCase();

  return (
    <View style={styles.postCard}>
      {/* 1. Header: Publisher profile + Handle + Follow button */}
      <View style={styles.postHeaderRow}>
        <TouchableOpacity
          style={styles.publisherInfo}
          onPress={() => onPressPublisher(publisherHandle, publisherName, item.publisher_avatar || '')}
          activeOpacity={0.8}
        >
          {item.publisher_avatar ? (
            <Image source={{ uri: item.publisher_avatar }} style={styles.publisherAvatarImg} />
          ) : (
            <View style={[styles.publisherAvatarCircle, { backgroundColor: borderColor }]}>
              <Text style={styles.publisherAvatarLetter}>{publisherInitial}</Text>
            </View>
          )}

          <View style={styles.publisherNameCol}>
            <Text style={styles.publisherNameText} numberOfLines={1}>
              {publisherName}
            </Text>
            <Text style={styles.publisherHandleSubtext} numberOfLines={1}>
              {publisherHandle}
            </Text>
          </View>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.followBtn,
            item.is_following ? styles.followingBtnActive : styles.followBtnDefault,
          ]}
          onPress={() => onToggleFollow(publisherHandle, !!item.is_following)}
          activeOpacity={0.75}
        >
          <Text style={[styles.followBtnText, item.is_following && styles.followingBtnText]}>
            {item.is_following ? 'Following' : 'Follow'}
          </Text>
        </TouchableOpacity>
      </View>

      {/* 2. Hero Media: Large Avatar Image with Floating Chat Bubble */}
      <TouchableOpacity
        style={styles.mediaContainer}
        onPress={handleMediaPress}
        activeOpacity={0.96}
      >
        {item.image_url ? (
          <Image
            source={{ uri: item.image_url }}
            style={styles.mediaImage}
            resizeMode="cover"
          />
        ) : (
          <View style={[styles.mediaFallback, { backgroundColor: '#13131F' }]}>
            <View style={[styles.fallbackSquircle, { borderColor }]}>
              <Text style={[styles.fallbackLetter, { color: borderColor }]}>
                {item.name ? item.name.charAt(0).toUpperCase() : 'A'}
              </Text>
            </View>
            <Text style={styles.fallbackName}>{item.name}</Text>
          </View>
        )}

        {/* Floating Top-Right Chat Bubble (exactly matching Chai screenshot) */}
        <TouchableOpacity
          style={styles.floatingChatBadge}
          onPress={() => onInitiateChat(item)}
          activeOpacity={0.8}
        >
          <FloatingChatBubble size={16} color="#FFFFFF" />
        </TouchableOpacity>

        {/* Double-tap animated heart pop in center */}
        <Animated.View
          pointerEvents="none"
          style={[
            styles.centeredPopHeart,
            {
              transform: [{ scale: heartScaleAnim }],
              opacity: heartOpacityAnim,
            },
          ]}
        >
          <HeartIcon size={96} filled color="#F43F5E" />
        </Animated.View>
      </TouchableOpacity>

      {/* 3. Action Bar: Like & Share & Quick Chat */}
      <View style={styles.actionBarRow}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => onToggleLike(item.id, !!item.is_liked)}
          activeOpacity={0.7}
          accessibilityLabel={`Like ${item.name}`}
        >
          <HeartIcon size={22} filled={!!item.is_liked} color="#FFFFFF" />
          <Text style={[styles.actionCountText, item.is_liked && styles.actionCountLiked]}>
            {formatCount(item.likes_count)}
          </Text>
        </TouchableOpacity>

        {/* Persona Share Button (right side of Like button) */}
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => onSharePersona(item)}
          activeOpacity={0.7}
          accessibilityLabel={`Share ${item.name}`}
        >
          <ShareIcon size={21} color="#FFFFFF" />
        </TouchableOpacity>

        <View style={{ flex: 1 }} />

        {/* Direct quick chat CTA button */}
        <TouchableOpacity
          style={[styles.quickChatBtn, { borderColor }]}
          onPress={() => onInitiateChat(item)}
          activeOpacity={0.8}
        >
          <Text style={[styles.quickChatBtnText, { color: borderColor }]}>
            Chat with {item.name}
          </Text>
        </TouchableOpacity>
      </View>

      {/* 4. Caption: Publisher name + Avatar name + Tagline / First message */}
      <View style={styles.captionContainer}>
        <Text style={styles.captionText}>
          <Text style={styles.captionPublisherBold}>{publisherName} </Text>
          <Text style={styles.captionAvatarTitle}>{item.name}</Text>
          {item.tagline ? (
            <Text style={styles.captionTaglineText}> ({item.tagline})</Text>
          ) : null}
        </Text>

        {item.greeting ? (
          <View style={styles.openerPreviewBox}>
            <Text
              style={styles.openerText}
              numberOfLines={expanded ? undefined : 2}
            >
              {item.greeting}
            </Text>
            {item.greeting.length > 70 ? (
              <TouchableOpacity
                onPress={() => setExpanded(!expanded)}
                activeOpacity={0.7}
                style={styles.moreBtn}
              >
                <Text style={styles.moreBtnText}>
                  {expanded ? 'less' : '... more'}
                </Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ) : null}
      </View>
    </View>
  );
});

export default function HomeScreen() {
  const { user } = useAuth();
  const [feedItems, setFeedItems] = useState<FeedPersonaItem[]>([]);
  const [page, setPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [selectedPersona, setSelectedPersona] = useState<PersonaItem | null>(null);
  const [selectedPublisher, setSelectedPublisher] = useState<{
    handle: string;
    name: string;
    avatar: string;
  } | null>(null);
  const [activeChatPersona, setActiveChatPersona] = useState<PersonaItem | null>(null);

  // Load Initial Page
  const loadInitialFeed = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const resp = await fetchFeedPage(1, 4, isRefresh, user?.id);
      setFeedItems(resp.results);
      setPage(1);
      setHasMore(resp.has_more);
    } catch (err) {
      console.warn('[HomeScreen] Feed load error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  useEffect(() => {
    loadInitialFeed(false);
  }, [loadInitialFeed]);

  // Load next page on scroll reached
  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !hasMore || loading || refreshing) return;
    setLoadingMore(true);

    try {
      const nextPage = page + 1;
      const resp = await fetchFeedPage(nextPage, 4, false, user?.id);
      if (resp.results.length > 0) {
        setFeedItems((prev) => {
          // Merge avoiding duplicates by id
          const existingIds = new Set(prev.map((p) => p.id));
          const uniqueNew = resp.results.filter((p) => !existingIds.has(p.id));
          return [...prev, ...uniqueNew];
        });
        setPage(nextPage);
        setHasMore(resp.has_more);
      } else {
        setHasMore(false);
      }
    } catch (err) {
      console.warn('[HomeScreen] Load more error:', err);
    } finally {
      setLoadingMore(false);
    }
  }, [page, hasMore, loadingMore, loading, refreshing, user?.id]);

  // Optimistic Like Toggle with authoritative database sync
  const handleToggleLike = useCallback(async (personaId: string, currentLiked: boolean) => {
    // 1. Instant optimistic UI update
    setFeedItems((prev) =>
      prev.map((item) => {
        if (item.id === personaId) {
          const willBeLiked = !currentLiked;
          return {
            ...item,
            is_liked: willBeLiked,
            likes_count: Math.max(0, item.likes_count + (willBeLiked ? 1 : -1)),
          };
        }
        return item;
      })
    );
    // 2. Sync with database and update with server's exact count
    const res = await togglePersonaLike(personaId, currentLiked, user?.id);
    if (typeof res.server_likes_count === 'number') {
      setFeedItems((prev) =>
        prev.map((item) =>
          item.id === personaId
            ? { ...item, is_liked: res.liked, likes_count: res.server_likes_count! }
            : item
        )
      );
    }
  }, [user?.id]);

  // Optimistic Follow Toggle
  const handleToggleFollow = useCallback(async (handle: string, currentFollowing: boolean) => {
    // Instant optimistic UI update for all posts by this publisher
    setFeedItems((prev) =>
      prev.map((item) => {
        if (
          item.publisher_handle === handle ||
          item.publisher_name === handle
        ) {
          return {
            ...item,
            is_following: !currentFollowing,
          };
        }
        return item;
      })
    );
    await togglePublisherFollow(handle, currentFollowing, user?.id);
  }, [user?.id]);

  // Initiate Real Interactive Chat
  const handleInitiateChat = useCallback((p: FeedPersonaItem | PersonaItem) => {
    setActiveChatPersona(p);
  }, []);

  // Share Persona handler via native OS share sheet
  const handleSharePersona = useCallback(async (persona: FeedPersonaItem) => {
    try {
      const shareUrl = `https://amour.ai/p/${persona.id}`;
      const intro = persona.tagline || persona.greeting || 'Meet my AI companion on Amour!';
      await Share.share({
        title: `Chat with ${persona.name}`,
        message: `Chat with ${persona.name} on Amour AI!\n\n"${intro}"\n\n${shareUrl}`,
      });
    } catch (err) {
      console.warn('[Share] Error sharing persona:', err);
    }
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: FeedPersonaItem }) => (
      <FeedPostCard
        item={item}
        onPressProfile={(p) => setSelectedPersona(p)}
        onPressPublisher={(handle, name, avatar) =>
          setSelectedPublisher({ handle, name, avatar })
        }
        onInitiateChat={handleInitiateChat}
        onToggleLike={handleToggleLike}
        onToggleFollow={handleToggleFollow}
        onSharePersona={handleSharePersona}
      />
    ),
    [handleInitiateChat, handleToggleLike, handleToggleFollow, handleSharePersona]
  );

  const renderFooter = () => {
    if (!loadingMore) return <View style={styles.listFooterPadding} />;
    return (
      <View style={styles.loadingMoreContainer}>
        <ActivityIndicator size="small" color="#F43F5E" />
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      {/* Top Header - Chai / Instagram Style */}
      <View style={styles.topHeader}>
        <View style={styles.headerLogoRow}>
          <AmourLogoVector size={30} showText={false} animated={false} />
          <Text style={styles.headerBrandText}>AMOUR</Text>
        </View>
      </View>

      {/* Main Feed Content */}
      {loading ? (
        <View style={styles.centerLoading}>
          <ActivityIndicator size="large" color="#F43F5E" />
        </View>
      ) : feedItems.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyTitle}>No Community Avatars Yet</Text>
          <Text style={styles.emptySubtitle}>
            Be the first to create and publish a companion to the community feed.
          </Text>
          <TouchableOpacity
            style={styles.primaryCreateBtn}
            onPress={() => router.push('/(tabs)/create')}
            activeOpacity={0.85}
          >
            <Text style={styles.primaryCreateBtnText}>Create Companion</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => loadInitialFeed(true)}
            activeOpacity={0.8}
          >
            <Text style={styles.retryBtnText}>Refresh Feed</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={feedItems}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          showsVerticalScrollIndicator={false}
          onEndReached={handleLoadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={renderFooter}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => loadInitialFeed(true)}
              tintColor="#F43F5E"
              colors={['#F43F5E']}
            />
          }
          // Memory & Rendering Optimizations
          removeClippedSubviews={Platform.OS === 'android'}
          windowSize={5}
          maxToRenderPerBatch={3}
          initialNumToRender={2}
          updateCellsBatchingPeriod={50}
        />
      )}

      {/* Persona Detail Modal */}
      <PersonaDetailModal
        visible={!!selectedPersona}
        persona={selectedPersona}
        onClose={() => setSelectedPersona(null)}
        onInitiateChat={(p) => {
          setSelectedPersona(null);
          handleInitiateChat(p);
        }}
      />

      {/* Publisher Profile Modal */}
      <PublisherProfileModal
        visible={!!selectedPublisher}
        publisherHandle={selectedPublisher?.handle || null}
        initialPublisherName={selectedPublisher?.name}
        initialPublisherAvatar={selectedPublisher?.avatar}
        userId={user?.id}
        onClose={() => setSelectedPublisher(null)}
        onSelectPersona={(persona) => {
          setSelectedPublisher(null);
          setSelectedPersona(persona);
        }}
        onToggleFollowParent={handleToggleFollow}
      />

      {/* Real Interactive Chat Modal */}
      <CompanionChatModal
        visible={!!activeChatPersona}
        persona={activeChatPersona}
        onClose={() => setActiveChatPersona(null)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#000000',
  },
  topHeader: {
    height: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#12121A',
    backgroundColor: '#000000',
  },
  headerLogoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  headerBrandText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 22,
    letterSpacing: 1.2,
  },

  centerLoading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyTitle: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
  },
  emptySubtitle: {
    color: '#9CA3AF',
    fontSize: 13,
    textAlign: 'center',
  },
  primaryCreateBtn: {
    marginTop: 6,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
    backgroundColor: '#F43F5E',
  },
  primaryCreateBtnText: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 15,
    letterSpacing: 0.5,
  },
  retryBtn: {
    marginTop: 4,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    backgroundColor: '#1E1E2A',
  },
  retryBtnText: {
    color: '#F43F5E',
    fontWeight: '600',
    fontSize: 13,
  },

  // Post Card (Instagram / Chai style)
  postCard: {
    marginBottom: 20,
    backgroundColor: '#000000',
  },
  postHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  publisherInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
  },
  publisherAvatarImg: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#1E1E2A',
  },
  publisherAvatarCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  publisherAvatarLetter: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },
  publisherNameCol: {
    flex: 1,
  },
  publisherNameText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
    letterSpacing: 0.2,
  },
  publisherHandleSubtext: {
    color: '#9CA3AF',
    fontSize: 11,
    marginTop: 1,
  },

  followBtn: {
    paddingHorizontal: 16,
    paddingVertical: 5,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  followBtnDefault: {
    borderColor: '#FFFFFF',
    backgroundColor: 'transparent',
  },
  followingBtnActive: {
    borderColor: '#374151',
    backgroundColor: '#1F2937',
  },
  followBtnText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 12,
  },
  followingBtnText: {
    color: '#9CA3AF',
  },

  // Media
  mediaContainer: {
    width: width,
    height: MEDIA_HEIGHT,
    backgroundColor: '#0A0A10',
    position: 'relative',
    overflow: 'hidden',
  },
  mediaImage: {
    width: '100%',
    height: '100%',
  },
  mediaFallback: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  fallbackSquircle: {
    width: 100,
    height: 100,
    borderRadius: 30,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#161622',
  },
  fallbackLetter: {
    fontSize: 42,
    fontWeight: '700',
  },
  fallbackName: {
    color: '#FFFFFF',
    fontFamily: 'ChangaOne-Regular',
    fontSize: 18,
  },

  floatingChatBadge: {
    position: 'absolute',
    top: 14,
    right: 14,
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },

  centeredPopHeart: {
    position: 'absolute',
    top: MEDIA_HEIGHT / 2 - 48,
    left: width / 2 - 48,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Action Bar
  actionBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingTop: 10,
    paddingBottom: 6,
    gap: 16,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  actionCountText: {
    color: '#E5E7EB',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  actionCountLiked: {
    color: '#F43F5E',
  },

  quickChatBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  quickChatBtnText: {
    fontWeight: '600',
    fontSize: 12,
  },

  // Caption
  captionContainer: {
    paddingHorizontal: 14,
    paddingBottom: 6,
  },
  captionText: {
    color: '#F3F4F6',
    fontSize: 13,
    lineHeight: 18,
  },
  captionPublisherBold: {
    fontWeight: '700',
    color: '#FFFFFF',
  },
  captionAvatarTitle: {
    fontWeight: '600',
    color: '#F3F4F6',
  },
  captionTaglineText: {
    color: '#9CA3AF',
  },

  openerPreviewBox: {
    marginTop: 4,
  },
  openerText: {
    color: '#D1D5DB',
    fontSize: 13,
    lineHeight: 18,
    fontStyle: 'italic',
  },
  moreBtn: {
    marginTop: 2,
    alignSelf: 'flex-start',
  },
  moreBtnText: {
    color: '#6B7280',
    fontSize: 12,
    fontWeight: '600',
  },

  loadingMoreContainer: {
    paddingVertical: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  listFooterPadding: {
    height: 40,
  },
});
