import React, { createContext, useContext, useEffect, useRef } from "react";
import { Animated, Easing, Platform, ScrollView, ScrollViewProps, StyleSheet, useWindowDimensions, View } from "react-native";

type Listener = () => void;
const RevealCtx = createContext<{ subscribe: (fn: Listener) => () => void } | null>(null);

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
    // Real DOM scroller, FIXED to the visual viewport. This deliberately
    // escapes the expo-router ancestor chain (nested absolute/flex divs whose
    // height is computed once at first load): iOS Safari sizes and repaints
    // position:fixed scrollers directly against the viewport, which fixes the
    // "content clipped/blank strip until refresh" bug on mobile first load.
    const flat = StyleSheet.flatten(style) as any;
    return (
      <RevealCtx.Provider value={ctx}>
        <div
          onScroll={emitScroll}
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            overflowY: "auto",
            overflowX: "hidden",
            touchAction: "pan-y",
            backgroundColor: flat?.backgroundColor,
          }}
        >
          <View style={contentContainerStyle}>{children}</View>
        </div>
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
