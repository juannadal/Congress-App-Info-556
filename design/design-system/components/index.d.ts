import type * as React from 'react';

export interface SearchBarProps {
  /** Controlled query text. Leave undefined for an uncontrolled field. */
  value?: string;
  /** Starting query for an uncontrolled field. */
  defaultValue?: string;
  /** Shown while the field is empty. Default: "Ask in everyday words". */
  placeholder?: string;
  /** Accessible name of the field. Default: "Search member biographies". */
  label?: string;
  /** Default: "Search". */
  buttonLabel?: string;
  /** Form field name. Default: "q". */
  name?: string;
  onChange?: (query: string) => void;
  onSubmit?: (query: string) => void;
  className?: string;
}
export declare function SearchBar(props: SearchBarProps): React.ReactElement;

export interface FilterChipProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Whether this filter is applied. Sets aria-pressed. */
  selected?: boolean;
  /** How many passages (or members) match with this filter on. */
  count?: number | string;
  /** The filter's value: "Senate", "Democrat", "California". */
  children?: React.ReactNode;
}
export declare function FilterChip(props: FilterChipProps): React.ReactElement;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** "primary" is the ink fill, once per view. Default: "quiet". */
  variant?: 'primary' | 'quiet';
}
export declare function Button(props: ButtonProps): React.ReactElement;

export interface ResultCardProps {
  /** 1-based position in the ranked list. */
  rank?: number;
  /** The member's name as the article titles it. */
  name: string;
  /** "Senator" or "Representative". */
  chamber?: string;
  party?: 'D' | 'R' | 'I';
  /** Full state name: "California". */
  state?: string;
  /** House district, shown after the state: "12th district". */
  district?: string;
  /** Portrait URL. Without it the card shows the member's initials. */
  photo?: string;
  /** Link to the Wikipedia article (the recorded revision). */
  href?: string;
  /** The retrieval score line, already formatted: "BM25 14.82". */
  score?: string;
  /** The passage text. Wrap each matched term in a mark element. */
  children?: React.ReactNode;
  className?: string;
}
export declare function ResultCard(props: ResultCardProps): React.ReactElement;

export interface PartyTagProps {
  party: 'D' | 'R' | 'I';
  /** Letter only, for dense tables. The word stays available as a title. */
  short?: boolean;
  className?: string;
}
export declare function PartyTag(props: PartyTagProps): React.ReactElement;

export interface MethodTagProps {
  method: 'keyword' | 'semantic' | 'hybrid';
  /** Show the technique after the name (BM25, MiniLM, RRF). Default: true. */
  detail?: boolean;
  className?: string;
}
export declare function MethodTag(props: MethodTagProps): React.ReactElement;

export interface RelevanceProps {
  /** 0 not relevant, 1 partly relevant, 2 relevant. */
  grade: 0 | 1 | 2;
  className?: string;
}
export declare function Relevance(props: RelevanceProps): React.ReactElement;

export interface MetricTileProps {
  /** The metric's name exactly: "nDCG@10", "Recall@10", "MRR". */
  label: string;
  /** The value, already formatted to three decimals: "0.742". */
  value: string;
  /** Which method this value belongs to. */
  method?: 'keyword' | 'semantic' | 'hybrid';
  /** One short line under the value: the query group or sample size. */
  note?: string;
  className?: string;
}
export declare function MetricTile(props: MetricTileProps): React.ReactElement;

declare global {
  interface Window {
    BioSearch: {
      SearchBar: typeof SearchBar;
      FilterChip: typeof FilterChip;
      Button: typeof Button;
      ResultCard: typeof ResultCard;
      PartyTag: typeof PartyTag;
      MethodTag: typeof MethodTag;
      Relevance: typeof Relevance;
      MetricTile: typeof MetricTile;
    };
  }
}
