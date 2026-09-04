import { StyleSheet, Text } from "react-native";

import { RichPalette } from "./paper-theme";
import { htmlToPlain } from "@/src/utils/richtext";

/** Native fallback: renders the quotation body as readable plain text. */
export default function RichHtml({
  html,
  palette,
  fontSize = 14,
  lineHeight = 22,
  testID,
}: {
  html: string;
  palette: RichPalette;
  fontSize?: number;
  lineHeight?: number;
  testID?: string;
}) {
  return (
    <Text testID={testID} style={[styles.text, { color: palette.text, fontSize, lineHeight }]}>
      {htmlToPlain(html)}
    </Text>
  );
}

const styles = StyleSheet.create({
  text: { marginTop: 4 },
});
