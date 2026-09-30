/**
 * The Recipe extractor: what counts as a recipe, and what must never be treated as one.
 *
 * 448 of 1279 posts are recipes and none of them was eligible for Google's Recipe rich result,
 * because every post emitted BlogPosting and nothing else. This is the logic that changed that,
 * and it is unit-tested rather than only verified against the export because the two failure
 * directions are both expensive:
 *
 *   under-matching  a recipe silently stays ineligible, and nothing reports it. The first
 *                   version of extractRecipe() required an ORDERED_LIST for the steps and
 *                   covered 108 of 448 - it looked like it worked.
 *   over-matching   an essay acquires a Recipe node. That is a false structured-data claim
 *                   about a page, which is the category of mistake that earns a manual action.
 */
import { describe, expect, it } from 'vitest';
import { extractRecipe, recipeSchema, type RecipeRicosNode } from '../lib/recipe-schema';

const heading = ( text: string, level = 2 ): RecipeRicosNode => ( {
  type: 'HEADING', headingData: { level }, nodes: [ { type: 'TEXT', textData: { text } } ],
} );
const para = ( text: string ): RecipeRicosNode => ( {
  type: 'PARAGRAPH', nodes: [ { type: 'TEXT', textData: { text } } ],
} );
const item = ( text: string ): RecipeRicosNode => ( {
  type: 'LIST_ITEM', nodes: [ para( text ) ],
} );
const bulleted = ( ...texts: string[] ): RecipeRicosNode => ( {
  type: 'BULLETED_LIST', nodes: texts.map( item ),
} );
const ordered = ( ...texts: string[] ): RecipeRicosNode => ( {
  type: 'ORDERED_LIST', nodes: texts.map( item ),
} );

describe( 'extractRecipe', () => {
  it( 'reads a list of ingredients and a numbered method', () => {
    const parts = extractRecipe( [
      para( 'A note about the dish.' ),
      heading( 'Ingredients' ), bulleted( '2 cups rice', '1 tsp salt' ),
      heading( 'Method' ), ordered( 'Rinse the rice.', 'Boil for ten minutes.' ),
    ] );
    expect( parts ).toEqual( {
      ingredients: [ '2 cups rice', '1 tsp salt' ],
      instructions: [ 'Rinse the rice.', 'Boil for ten minutes.' ],
    } );
  } );

  it( 'reads a method written as PROSE, which is how 340 of the 448 are written', () => {
    /*
     * THE BUG THIS PINS. Requiring an ordered list covered 108 of 448 recipes. The rendered
     * HTML of the failures reads `h2 ul li li ... h2 p` - ingredients itemised, method in
     * sentences - so the steps were being discarded on three quarters of the corpus while the
     * feature looked like it worked.
     */
    const parts = extractRecipe( [
      heading( 'Ingredients' ), bulleted( '1 acorn squash' ),
      heading( 'Method' ),
      para( 'Roast the squash until soft.' ),
      para( 'Blend with stock and season.' ),
    ] );
    expect( parts?.instructions ).toEqual( [
      'Roast the squash until soft.', 'Blend with stock and season.',
    ] );
  } );

  it( 'prefers the list when a section has both a list and prose', () => {
    // The list is the author's own itemisation, so it wins over surrounding commentary.
    const parts = extractRecipe( [
      heading( 'Ingredients' ), bulleted( 'flour' ),
      heading( 'Method' ),
      para( 'This is easier than it looks.' ),
      ordered( 'Mix.', 'Bake.' ),
    ] );
    expect( parts?.instructions ).toEqual( [ 'Mix.', 'Bake.' ] );
  } );

  it( 'stops collecting at a heading that opens neither section', () => {
    // A list under Notes or Variations is not part of the method.
    const parts = extractRecipe( [
      heading( 'Ingredients' ), bulleted( 'dal' ),
      heading( 'Method' ), ordered( 'Simmer.' ),
      heading( 'Notes' ), ordered( 'Keeps for two days.' ),
      heading( 'Variations' ), para( 'Add tamarind.' ),
    ] );
    expect( parts?.instructions ).toEqual( [ 'Simmer.' ] );
  } );

  it( 'accepts the synonyms a human author would reach for', () => {
    for ( const steps of [ 'Instructions', 'Directions', 'Steps', 'Preparation' ] ) {
      expect( extractRecipe( [
        heading( 'You will need' ), bulleted( 'water' ),
        heading( steps ), ordered( 'Boil it.' ),
      ] ), steps ).not.toBeNull();
    }
  } );

  it( 'returns null unless BOTH halves are present', () => {
    expect( extractRecipe( [ heading( 'Ingredients' ), bulleted( 'salt' ) ] ) ).toBeNull();
    expect( extractRecipe( [ heading( 'Method' ), ordered( 'Stir.' ) ] ) ).toBeNull();
    expect( extractRecipe( [] ) ).toBeNull();
    expect( extractRecipe( undefined ) ).toBeNull();
  } );

  it( 'does not turn an essay into a recipe', () => {
    /*
     * THE OVER-MATCHING CASE, and the reason both halves are required. 831 posts in this corpus
     * are not recipes, and plenty of them contain a list under a heading. Requiring an
     * ingredient section is what keeps an essay about process out of the recipe index.
     */
    expect( extractRecipe( [
      heading( 'Three steps to a clearer decision' ),
      ordered( 'Name the problem.', 'Name the constraint.', 'Choose.' ),
      heading( 'Steps' ), ordered( 'Write it down.' ),
    ] ) ).toBeNull();
  } );

  it( 'ignores a list nested inside another block', () => {
    // A quoted list is not the recipe's method; only top-level nodes are walked.
    const parts = extractRecipe( [
      heading( 'Ingredients' ), bulleted( 'ghee' ),
      heading( 'Method' ),
      { type: 'BLOCKQUOTE', nodes: [ ordered( 'Somebody else said to do this.' ) ] },
      para( 'Warm the ghee.' ),
    ] );
    expect( parts?.instructions ).toEqual( [ 'Warm the ghee.' ] );
  } );

  it( 'flattens decorated text without keeping the markup', () => {
    const parts = extractRecipe( [
      heading( 'Ingredients' ),
      { type: 'BULLETED_LIST', nodes: [ { type: 'LIST_ITEM', nodes: [ {
        type: 'PARAGRAPH', nodes: [
          { type: 'TEXT', textData: { text: '2 tbsp ' } },
          { type: 'TEXT', textData: { text: 'toasted' } },
          { type: 'TEXT', textData: { text: ' sesame oil' } },
        ],
      } ] } ] },
      heading( 'Method' ), ordered( 'Heat.' ),
    ] );
    expect( parts?.ingredients ).toEqual( [ '2 tbsp toasted sesame oil' ] );
  } );
} );

describe( 'recipeSchema', () => {
  const parts = { ingredients: [ 'a', 'b' ], instructions: [ 'first', 'second' ] };
  const node = recipeSchema( {
    parts,
    name: 'Agathi Leaves Fry',
    description: 'A short description.',
    canonical: 'https://wecare.digital/post/agathi-leaves-fry/',
    image: { '@type': 'ImageObject', url: 'https://example.test/x.png', width: 1, height: 1 },
    datePublished: '2026-09-29T11:37:07.537Z',
    authorName: 'Anew by WECARE.DIGITAL',
    publisherId: 'https://wecare.digital/#organization',
  } );

  it( 'carries every property Google documents as required', () => {
    expect( node[ '@type' ] ).toBe( 'Recipe' );
    for ( const required of [ 'name', 'image', 'recipeIngredient', 'recipeInstructions' ] ) {
      expect( node[ required ], required ).toBeTruthy();
    }
  } );

  it( 'INVENTS NOTHING', () => {
    /*
     * The strongest Recipe enhancers are prepTime, cookTime, recipeYield, nutrition and
     * aggregateRating. None exists in this corpus and none may be guessed: a fabricated
     * aggregateRating was already removed from this site once, and a guessed cookTime is a
     * factual claim about a dish published under the company's name. A node with fewer honest
     * properties is eligible; a node with invented ones is a lie that also risks a manual
     * action. This is the assertion that keeps it that way.
     */
    for ( const invented of [
      'aggregateRating', 'review', 'prepTime', 'cookTime', 'totalTime',
      'recipeYield', 'nutrition', 'recipeCuisine', 'recipeCategory',
    ] ) {
      expect( node, invented ).not.toHaveProperty( invented );
    }
  } );

  it( 'numbers the steps from one and keeps their order', () => {
    expect( node.recipeInstructions ).toEqual( [
      { '@type': 'HowToStep', position: 1, text: 'first' },
      { '@type': 'HowToStep', position: 2, text: 'second' },
    ] );
  } );

  it( 'references the Organization by @id instead of restating it', () => {
    // One copy of the company's identity in the graph, as with the BlogPosting node.
    expect( node.publisher ).toEqual( { '@id': 'https://wecare.digital/#organization' } );
  } );

  it( 'ties itself to the page and to a per-route @id', () => {
    expect( node[ '@id' ] ).toBe( 'https://wecare.digital/post/agathi-leaves-fry/#recipe' );
    expect( node.mainEntityOfPage )
      .toEqual( { '@id': 'https://wecare.digital/post/agathi-leaves-fry/#webpage' } );
  } );

  it( 'omits description and datePublished rather than emitting empty ones', () => {
    const bare = recipeSchema( {
      parts, name: 'X', canonical: 'https://wecare.digital/post/x/', image: {},
      publisherId: 'https://wecare.digital/#organization',
    } );
    expect( bare ).not.toHaveProperty( 'description' );
    expect( bare ).not.toHaveProperty( 'datePublished' );
  } );
} );
