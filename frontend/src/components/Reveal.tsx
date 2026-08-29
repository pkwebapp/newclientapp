import React, { createContext, useContext, useEffect, useRef } from "react";
import { Animated, Easing, Platform, ScrollView, ScrollViewProps, useWindowDimensions, View } from "react-native";

type Listener = () => void;
const RevealCtx = createContext<{ subscribe: (fn: Listener) => () => void } | null>(null);
const WebScrollView = View as any;

/** Scroll container that notifies child <Reveal> blocks on scroll. */
export function RevealScroll({ children, onScroll, contentContainerStyle, style, ...props }: ScrollViewProps) {
  const listeners = useRef(new Set<Listener>()).current;
  const ctx = useRef({
    subscribe: (fn: Listener) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  }).current;
  const emitScroll = (e: any) => {
    onScroll?.(e);
    listeners.forEach((fn) => fn());
  };

  if (Platform.OS === "web") {
    return (
      <RevealCtx.Provider value={ctx}>
        <WebScrollView
          style={[
            {
              flex: 1,
              overflow: "auto",
              touchAction: "pan-y",
              WebkitOverflowScrolling: "touch",
            } as any,
            style,
          ]}
          onScroll={emitScroll}
        >
          <View style={contentContainerStyle}>{children}</View>
        </WebScrollView>
      </RevealCtx.Provider>
    );
  }

  return (
    <RevealCtx.Provider value={ctx}>
      <ScrollView
        {...props}
        style={style}
        contentContainerStyle={contentContainerStyle}
        scrollEventThrottle={32}
        onScroll={emitScroll}
      >
        {children}
      </ScrollView>
    </RevealCtx.Provider>
  );
}

/** Gently fades + slides content in the first time it scrolls into view. */
export function Reveal({ children, delay = 0, style }: { children: React.ReactNode; delay?: number; style?: any }) {
  const ctx = useContext(RevealCtx);
  const { height: winH } = useWindowDimensions();
  const anim = useRef(new Animated.Value(0)).current;
  const shown = useRef(false);
  const ref = useRef<any>(null);

  useEffect(() => {
    const check = () => {
      if (shown.current || !ref.current?.measureInWindow) return;
      ref.current.measureInWindow((_x: number, y: number, _w: number, h: number) => {
        if (y < winH * 0.92 && y + (h || 0) > 0) {
          shown.current = true;
          Animated.timing(anim, { toValue: 1, duration: 650, delay, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
        }
      });
    };
    const t = setTimeout(check, 180); // catch content already above the fold
    const unsub = ctx?.subscribe(check);
    return () => {
      clearTimeout(t);
      unsub?.();
    };
  }, [ctx, winH, anim, delay]);

  return (
    <Animated.View
      ref={ref}
      style={[
        style,
        {
          opacity: anim,
          transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [26, 0] }) }],
        },
      ]}
    >
      {children}
    </Animated.View>
  );
}
