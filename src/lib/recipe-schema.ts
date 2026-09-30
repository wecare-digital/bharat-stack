/**
 * Recipe structured data, derived from what a post already contains.
 *
 * WHY THIS EXISTS. Measured 2026-09-30 over the built export: 448 of 1279 posts carry an
 * "Ingredients" heading - they are recipes - and ZERO of them emitted schema.org Recipe. All
 * 1279 emitted only BlogPosting. Google has a Recipe rich result, it is one of the strongest
 * available, and it does not care how long the page is. That matters here more than usual,
 * because the same audit found the corpus median at 232 words with nothing above 545: the
 * advice "write longer" is the wrong lever for a recipe, and scripts/blog_quality_v2.py already
 * says so in its own words - "a short pickle recipe is complete at 110 words, and declaring it
 * defective would be this file overruling a published standard it does not own."
 *
 * So the lever is eligibility, not length.
 *
 * AUTOMATIC BY CONSTRUCTION, which was the requirement. Nothing is hand-authored and no field
 * is added to the corpus: this reads the Ricos node tree the page already renders, so a NEW
 * recipe post is eligible the moment it is published, with no extra step for anyone. If the
 * structure is not there, nothing is emitted - see the null returns below.
 *
 * THE STRUCTURE IT RELIES ON IS MEASURED, NOT ASSUMED. Across all 448 recipes the headings are
 * identical: every one has an "Ingredients" heading followed by a bulleted list and a "Method"
 * heading followed by an ordered list. Counted: 448 "Ingredients", 448 "Method". That is why a
 * heading-then-list walk is safe rather than hopeful.
 *
 * WHAT IS DELIBERATELY NOT EMITTED, and this is the important half. Google documents
 * prepTime, cookTime, totalTime, recipeYield, nutrition and aggregateRating as strong
 * enhancers. None of them exist in this corpus, and inventing them is not an option:
 *   - a fabricated aggregateRating was already removed from this site once, and putting a
 *     rating on a page nobody rated is the exact defect that removal was for
 *   - a guessed cookTime is a factual claim about a dish, published under the company's name
 * A Recipe node with fewer honest properties is eligible. A Recipe node with invented ones is
 * a lie that also risks a manual action. So this emits only what the post actually says.
 */

/** The subset of the Ricos tree this needs. Structurally compatible with the page's own type. */
export interface RecipeRicosNode {
  type?: string;
  nodes?: RecipeRicosNode[];
  textData?: { text?: string };
  headingData?: { level?: number };
}

export interface RecipeParts {
  ingredients: string[];
  instructions: string[];
}

/**
 * Headings that introduce the ingredient list.
 *
 * "Ingredients" is the only one present in the corpus today. The synonyms are here because a
 * future post written by a person rather than a migration will reasonably use one of them, and
 * the cost of a miss is silent - the page simply stops being eligible, with nothing to notice.
 */
const INGREDIENT_HEADINGS = [ 'ingredient', 'you will need', 'what you need' ];

/** Headings that introduce the steps. "Method" is the corpus's word; the rest are common. */
const INSTRUCTION_HEADINGS = [ 'method', 'instruction', 'direction', 'steps', 'preparation', 'how to make' ];

/** Raw concatenation, with NO trimming - see plainText below for why that matters. */
function rawText ( node: RecipeRicosNode | undefined ): string {
  if ( !node ) return '';
  const own = node.textData?.text || '';
  return own + ( node.nodes || [] ).map( rawText ).join( '' );
}

/**
 * All the text under a node, flattened. Decorations are ignored: bold is not part of a name.
 *
 * WHITESPACE IS NORMALISED ONCE, AT THE TOP, AND THAT IS A BUG FIX RATHER THAN A STYLE CHOICE.
 * This was one recursive function that trimmed at every level, so a decorated ingredient -
 * which is common, because quantities are often bolded - lost the spaces between its runs:
 * the three TEXT nodes "2 tbsp " / "toasted" / " sesame oil" each got trimmed before being
 * joined and came out as "2 tbsptoastedsesame oil". Caught by a unit test built from exactly
 * that shape; it would have shipped corrupted recipeIngredient values to Google on every
 * recipe whose ingredients use any inline formatting.
 */
function plainText ( node: RecipeRicosNode | undefined ): string {
  return rawText( node ).replace( /\s+/g, ' ' ).trim();
}

/** Which section a heading opens, or null when it opens neither. */
function sectionOf ( heading: string ): 'ingredients' | 'instructions' | null {
  const text = heading.toLowerCase();
  if ( INGREDIENT_HEADINGS.some( word => text.includes( word ) ) ) return 'ingredients';
  if ( INSTRUCTION_HEADINGS.some( word => text.includes( word ) ) ) return 'instructions';
  return null;
}

/** The LIST_ITEM texts of a list node, dropping empties. */
function listItems ( node: RecipeRicosNode ): string[] {
  return ( node.nodes || [] )
    .filter( child => child.type === 'LIST_ITEM' )
    .map( plainText )
    .filter( Boolean );
}

/**
 * Pull the ingredient and step lists out of a post's Ricos nodes.
 *
 * Returns null unless BOTH are present, and that is a deliberate gate rather than caution. A
 * Recipe with no recipeIngredient is not a recipe Google can show, and more importantly: the
 * 831 non-recipe posts in this corpus must not acquire a Recipe node because one of them
 * happens to contain a list under a heading with the word "steps" in it. Requiring both halves
 * is what keeps an essay out of the recipe index.
 *
 * Walks TOP-LEVEL nodes only. A nested list inside a blockquote is not the recipe's method, and
 * a recursive search would happily collect one.
 */
export function extractRecipe ( nodes: RecipeRicosNode[] | undefined ): RecipeParts | null {
  if ( !nodes || !nodes.length ) return null;

  let section: 'ingredients' | 'instructions' | null = null;
  /*
   * LISTS AND PARAGRAPHS ARE COLLECTED SEPARATELY, and that is the whole reason this works on
   * the corpus rather than a quarter of it.
   *
   * The first version required an ORDERED_LIST for the steps. Built and measured: 108 of 448
   * recipes got a Recipe node and 340 did not. Reading the rendered HTML of the failures showed
   * why - the element sequence is `h2 ul li li ... h2 p`, so the ingredients ARE a list and the
   * method is PROSE PARAGRAPHS. Only 108 recipes in the corpus write their steps as a numbered
   * list; the other 340 write them as sentences under a "Method" heading.
   *
   * A list is the better source when there is one - it is the author's own itemisation - so a
   * list wins where both appear. Where there is no list, the paragraphs in that section are the
   * steps as written, and using them is reporting the post rather than inventing anything.
   */
  const listed: Record<'ingredients' | 'instructions', string[]> = { ingredients: [], instructions: [] };
  const prose: Record<'ingredients' | 'instructions', string[]> = { ingredients: [], instructions: [] };

  for ( const node of nodes ) {
    if ( node.type === 'HEADING' ) {
      // A heading that opens neither section CLOSES the current one, so a list or a paragraph
      // under "Notes" or "Variations" is not swept into the method.
      section = sectionOf( plainText( node ) );
      continue;
    }
    if ( !section ) continue;
    if ( node.type === 'BULLETED_LIST' || node.type === 'ORDERED_LIST' ) {
      listed[ section ].push( ...listItems( node ) );
    } else if ( node.type === 'PARAGRAPH' ) {
      const text = plainText( node );
      if ( text ) prose[ section ].push( text );
    }
  }

  const ingredients = listed.ingredients.length ? listed.ingredients : prose.ingredients;
  const instructions = listed.instructions.length ? listed.instructions : prose.instructions;

  if ( !ingredients.length || !instructions.length ) return null;
  return { ingredients, instructions };
}

export interface RecipeSchemaInput {
  parts: RecipeParts;
  name: string;
  description?: string;
  canonical: string;
  image: unknown;
  datePublished?: string;
  authorName?: string;
  /** The @id of the Organization node already in the graph, referenced rather than restated. */
  publisherId: string;
}

/**
 * The Recipe node. Only properties the post actually supports.
 *
 * `image` is passed in rather than built here because the page already computes the social card
 * as an ImageObject with dimensions, and Google documents image as REQUIRED for Recipe - the
 * same property whose absence made every post ineligible for the Article rich result until it
 * was added. One source for it, not two.
 *
 * recipeInstructions are HowToStep objects, not one joined string. A single string is valid and
 * markedly less useful: the step list is what a voice assistant reads out one at a time.
 */
export function recipeSchema ( input: RecipeSchemaInput ): Record<string, unknown> {
  return {
    '@type': 'Recipe',
    '@id': `${input.canonical}#recipe`,
    name: input.name,
    ...( input.description ? { description: input.description } : {} ),
    url: input.canonical,
    image: input.image,
    ...( input.datePublished ? { datePublished: input.datePublished } : {} ),
    author: { '@type': 'Organization', name: input.authorName || 'WECARE.DIGITAL' },
    publisher: { '@id': input.publisherId },
    recipeIngredient: input.parts.ingredients,
    recipeInstructions: input.parts.instructions.map( ( text, index ) => ( {
      '@type': 'HowToStep',
      position: index + 1,
      text,
    } ) ),
    // Ties the recipe to the page carrying it, the same way the BlogPosting node does. Without
    // it the Recipe reads as an entity that merely happens to live at this URL.
    mainEntityOfPage: { '@id': `${input.canonical}#webpage` },
  };
}
